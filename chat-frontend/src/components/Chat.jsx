import React, { useState, useEffect, useRef } from 'react';
import { Box, Typography, TextField, IconButton, Paper, Avatar, Divider, Button } from '@mui/material';
import { Send as SendIcon, Logout, Search } from '@mui/icons-material';
import { motion, AnimatePresence } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import { getChatHistory, getWsUrl } from '../services/api';

const Chat = () => {
  const [messages, setMessages] = useState([]);
  const [newMessage, setNewMessage] = useState('');
  const [contactId, setContactId] = useState('');
  const [activeContact, setActiveContact] = useState(null);
  const [ws, setWs] = useState(null);
  
  const messagesEndRef = useRef(null);
  const navigate = useNavigate();

  // Auto-scroll function
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    const token = localStorage.getItem('token');
    if (!token) {
      navigate('/');
      return;
    }

    // Step 4: Connect WebSocket
    const socket = new WebSocket(getWsUrl());
    
    socket.onopen = () => {
      console.log('WebSocket Connected');
    };

    // Step 7: Receive messages
    socket.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data);
        setMessages((prev) => [...prev, message]);
      } catch (e) {
        console.error('Error parsing message', e);
      }
    };

    socket.onclose = () => {
      console.log('WebSocket Disconnected');
    };

    setWs(socket);

    return () => {
      socket.close();
    };
  }, [navigate]);

  const loadHistory = async (id) => {
    try {
      // Step 5: Load chat history
      const history = await getChatHistory(id);
      setMessages(history);
      setActiveContact(id);
    } catch (err) {
      console.error('Failed to load history', err);
    }
  };

  const handleStartChat = (e) => {
    e.preventDefault();
    if (contactId) {
      loadHistory(parseInt(contactId));
    }
  };

  // Step 6: Send messages
  const handleSendMessage = (e) => {
    e.preventDefault();
    if (!newMessage.trim() || !activeContact || !ws) return;

    const payload = {
      receiver_id: activeContact,
      message: newMessage
    };

    ws.send(JSON.stringify(payload));
    setNewMessage('');
  };

  const handleLogout = () => {
    localStorage.removeItem('token');
    navigate('/');
  };

  return (
    <Box sx={{
      display: 'flex',
      height: '100vh',
      width: '100vw',
      p: 2,
      gap: 2
    }}>
      {/* Sidebar for "User List" workaround */}
      <Paper className="glass-panel" sx={{
        width: 300,
        display: 'flex',
        flexDirection: 'column',
        p: 2
      }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
          <Typography variant="h6" className="gradient-text" fontWeight="bold">
            Chats
          </Typography>
          <IconButton onClick={handleLogout} color="error" size="small">
            <Logout />
          </IconButton>
        </Box>
        
        <Box component="form" onSubmit={handleStartChat} sx={{ display: 'flex', gap: 1, mb: 3 }}>
          <TextField
            size="small"
            placeholder="Contact ID (e.g. 2)"
            value={contactId}
            onChange={(e) => setContactId(e.target.value)}
            fullWidth
          />
          <IconButton type="submit" color="primary">
            <Search />
          </IconButton>
        </Box>

        <Divider sx={{ mb: 2, borderColor: 'rgba(255,255,255,0.1)' }} />

        {activeContact && (
          <Box sx={{ 
            p: 2, 
            borderRadius: 2, 
            background: 'rgba(99, 102, 241, 0.15)',
            border: '1px solid rgba(99, 102, 241, 0.3)'
          }}>
            <Typography variant="subtitle2">Active Chat</Typography>
            <Typography variant="body2" color="text.secondary">Contact ID: {activeContact}</Typography>
          </Box>
        )}
      </Paper>

      {/* Main Chat Area */}
      <Paper className="glass-panel" sx={{
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden'
      }}>
        {activeContact ? (
          <>
            {/* Chat Header */}
            <Box sx={{ p: 2, borderBottom: '1px solid var(--glass-border)', display: 'flex', alignItems: 'center', gap: 2 }}>
              <Avatar sx={{ bgcolor: 'var(--primary)' }}>{activeContact}</Avatar>
              <Typography variant="h6">User {activeContact}</Typography>
            </Box>

            {/* Messages Area */}
            <Box sx={{
              flex: 1,
              p: 2,
              overflowY: 'auto',
              display: 'flex',
              flexDirection: 'column',
              gap: 2
            }}>
              <AnimatePresence>
                {messages.map((msg, index) => {
                  const isMine = msg.sender_id !== activeContact && msg.sender_id !== 0; // Assuming sender_id != activeContact is me
                  const isSystem = msg.sender_id === 0;

                  return (
                    <motion.div
                      key={msg.id || index}
                      initial={{ opacity: 0, scale: 0.8, y: 20 }}
                      animate={{ opacity: 1, scale: 1, y: 0 }}
                      transition={{ type: 'spring', stiffness: 500, damping: 30 }}
                      style={{
                        display: 'flex',
                        justifyContent: isSystem ? 'center' : (isMine ? 'flex-end' : 'flex-start'),
                        width: '100%'
                      }}
                    >
                      <Box sx={{
                        maxWidth: '70%',
                        p: 2,
                        borderRadius: 3,
                        background: isSystem 
                          ? 'rgba(255,255,255,0.1)'
                          : isMine 
                            ? 'linear-gradient(135deg, var(--primary), var(--secondary))' 
                            : 'var(--bg-input)',
                        borderBottomRightRadius: isMine ? 4 : 24,
                        borderBottomLeftRadius: !isMine && !isSystem ? 4 : 24,
                        boxShadow: isMine ? '0 4px 15px var(--primary-glow)' : 'none'
                      }}>
                        {isSystem && (
                          <Typography variant="caption" color="error" display="block" gutterBottom>
                            System Warning
                          </Typography>
                        )}
                        <Typography variant="body1" sx={{ wordBreak: 'break-word' }}>
                          {msg.message || msg.content}
                        </Typography>
                      </Box>
                    </motion.div>
                  );
                })}
              </AnimatePresence>
              <div ref={messagesEndRef} />
            </Box>

            {/* Input Area */}
            <Box component="form" onSubmit={handleSendMessage} sx={{
              p: 2,
              borderTop: '1px solid var(--glass-border)',
              display: 'flex',
              gap: 2
            }}>
              <TextField
                fullWidth
                placeholder="Type a message..."
                variant="outlined"
                value={newMessage}
                onChange={(e) => setNewMessage(e.target.value)}
                autoComplete="off"
              />
              <IconButton 
                type="submit" 
                disabled={!newMessage.trim()}
                sx={{ 
                  bgcolor: 'var(--primary)', 
                  color: 'white',
                  '&:hover': { bgcolor: 'var(--secondary)' },
                  '&.Mui-disabled': { bgcolor: 'rgba(255,255,255,0.1)', color: 'rgba(255,255,255,0.3)' }
                }}
              >
                <SendIcon />
              </IconButton>
            </Box>
          </>
        ) : (
          <Box sx={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', flexDirection: 'column' }}>
            <motion.div
              animate={{
                scale: [1, 1.1, 1],
                opacity: [0.5, 1, 0.5]
              }}
              transition={{ repeat: Infinity, duration: 3 }}
            >
              <Typography variant="h4" className="gradient-text" sx={{ opacity: 0.5 }}>
                Select a contact to start chatting
              </Typography>
            </motion.div>
          </Box>
        )}
      </Paper>
    </Box>
  );
};

export default Chat;
