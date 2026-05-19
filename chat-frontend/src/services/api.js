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

export const loginUser = async (email, password) => {
    const response = await api.post('/auth/login', { email, password });
    if (response.data.access_token) {
        localStorage.setItem('token', response.data.access_token);
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
