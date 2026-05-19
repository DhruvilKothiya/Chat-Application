import axios from 'axios';

const API_URL = 'http://localhost:8000';

const api = axios.create({
    baseURL: API_URL,
});

api.interceptors.request.use((config) => {
    const token = localStorage.getItem('token');
    if (token) {
        config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
});

// Add a response interceptor to handle token refresh
api.interceptors.response.use(
    (response) => response,
    async (error) => {
        const originalRequest = error.config;

        // If error is 401 and we haven't retried yet
        if (error.response?.status === 401 && !originalRequest._retry) {
            originalRequest._retry = true;
            
            try {
                const refreshToken = localStorage.getItem('refresh_token');
                if (!refreshToken) {
                    throw new Error("No refresh token available");
                }
                
                // Call refresh endpoint directly with axios to avoid infinite loop
                const response = await axios.post(`${API_URL}/auth/refresh`, {
                    refresh_token: refreshToken
                });
                
                const newAccessToken = response.data.access_token;
                const newRefreshToken = response.data.refresh_token;
                
                // Save new tokens
                localStorage.setItem('token', newAccessToken);
                localStorage.setItem('refresh_token', newRefreshToken);
                
                // Retry original request with new token
                originalRequest.headers.Authorization = `Bearer ${newAccessToken}`;
                return api(originalRequest);
                
            } catch (refreshError) {
                // If refresh fails, clear tokens and redirect to login
                localStorage.removeItem('token');
                localStorage.removeItem('refresh_token');
                window.location.href = '/';
                return Promise.reject(refreshError);
            }
        }
        
        return Promise.reject(error);
    }
);

export const loginUser = async (email, password) => {
    const response = await api.post('/auth/login', { email, password });
    if (response.data.access_token) {
        localStorage.setItem('token', response.data.access_token);
        if (response.data.refresh_token) {
            localStorage.setItem('refresh_token', response.data.refresh_token);
        }
    }
    return response.data;
};

export const registerUser = async (email, username, password) => {
    const response = await api.post('/auth/register', { email, username, password });
    return response.data;
};

export const getChatHistory = async (contactId) => {
    const response = await api.get(`/chat/history/${contactId}`);
    return response.data;
};

export const getWsUrl = () => {
    const token = localStorage.getItem('token');
    return `ws://localhost:8000/chat/ws?token=${token}`;
};
