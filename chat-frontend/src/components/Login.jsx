import React, { useState } from 'react';
import { Box, Typography, TextField, Button, Paper, Tabs, Tab } from '@mui/material';
import { motion } from 'framer-motion';
import { loginUser, registerUser } from '../services/api';
import { useNavigate } from 'react-router-dom';

const Login = () => {
  const [tab, setTab] = useState(0);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [username, setUsername] = useState('');
  const [error, setError] = useState('');
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    try {
      if (tab === 0) {
        // Login
        await loginUser(email, password);
        navigate('/chat');
      } else {
        // Register
        await registerUser(email, username, password);
        await loginUser(email, password);
        navigate('/chat');
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'An error occurred');
    }
  };

  return (
    <Box sx={{
      display: 'flex',
      justifyContent: 'center',
      alignItems: 'center',
      minHeight: '100vh',
      width: '100vw',
      padding: 2
    }}>
      <motion.div
        initial={{ opacity: 0, scale: 0.9, y: 20 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        transition={{ duration: 0.5, type: 'spring' }}
      >
        <Paper className="glass-panel" sx={{ p: 4, width: '100%', maxWidth: 400 }}>
          <Box sx={{ textAlign: 'center', mb: 3 }}>
            <Typography variant="h4" fontWeight="700" className="gradient-text" gutterBottom>
              Nexus Chat
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Connect in real-time, instantly.
            </Typography>
          </Box>

          <Tabs value={tab} onChange={(e, v) => setTab(v)} centered sx={{ mb: 3 }}>
            <Tab label="Login" />
            <Tab label="Register" />
          </Tabs>

          <form onSubmit={handleSubmit}>
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
              <TextField
                label="Email"
                type="email"
                variant="outlined"
                fullWidth
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
              {tab === 1 && (
                <TextField
                  label="Username"
                  variant="outlined"
                  fullWidth
                  required
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                />
              )}
              <TextField
                label="Password"
                type="password"
                variant="outlined"
                fullWidth
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />

              {error && (
                <Typography color="error" variant="body2" textAlign="center">
                  {error}
                </Typography>
              )}

              <Button
                type="submit"
                variant="contained"
                size="large"
                sx={{
                  mt: 2,
                  background: 'linear-gradient(135deg, var(--primary), var(--secondary))',
                  '&:hover': {
                    opacity: 0.9
                  }
                }}
              >
                {tab === 0 ? 'Sign In' : 'Sign Up'}
              </Button>
            </Box>
          </form>
        </Paper>
      </motion.div>
    </Box>
  );
};

export default Login;
