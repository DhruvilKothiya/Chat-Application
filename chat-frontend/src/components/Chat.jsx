import React, { useState, useEffect, useRef } from 'react';
import { Box, Typography, TextField, IconButton, Paper, Avatar, Divider, Badge } from '@mui/material';
import { Send as SendIcon, Logout, Search, Check, DoneAll } from '@mui/icons-material';
import { motion, AnimatePresence } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import { getChatHistory, getWsUrl } from '../services/api';

const Chat = () => {
  const [messages, setMessages] = useState([]);
  const [newMessage, setNewMessage] = useState('');
  const [contactUsernameInput, setContactUsernameInput] = useState('');
  const [activeContact, setActiveContact] = useState(null);
  const [activeUsername, setActiveUsername] = useState('');
  const [ws, setWs] = useState(null);
  const [isOnline, setIsOnline] = useState(false);
  const [isTyping, setIsTyping] = useState(false);
  
  const messagesEndRef = useRef(null);
  const typingTimeoutRef = useRef(null);
  const navigate = useNavigate();

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isTyping]);

  useEffect(() => {
    const token = localStorage.getItem('token');
    if (!token) {
      navigate('/');
      return;
    }

    const socket = new WebSocket(getWsUrl());
    let pingInterval;

    socket.onopen = () => {
      console.log('WebSocket Connected');
      // Start Ping Heartbeat to refresh Redis TTL
      pingInterval = setInterval(() => {
        if (socket.readyState === WebSocket.OPEN) {
          socket.send(JSON.stringify({ event: "ping" }));
        }
      }, 30000);
    };

    socket.onmessage = (eventData) => {
      try {
        const payload = JSON.parse(eventData.data);
        const { event, data } = payload;

        switch (event) {
          case 'receive_message':
          case 'message_sent':
            setMessages((prev) => {
              // Prevent duplicates
              if (prev.some(m => m.id === data.id)) return prev;
              return [...prev, data];
            });

            // If we are receiving, send an ACK back
            if (event === 'receive_message') {
              socket.send(JSON.stringify({
                event: "ack",
                data: { message_id: data.id }
              }));
              
              // If we are currently looking at this chat, mark it as seen!
              if (data.sender_id === activeContact) {
                socket.send(JSON.stringify({
                  event: "seen",
                  data: { message_id: data.id }
                }));
              }
            }
            break;

          case 'message_delivered':
            setMessages((prev) => prev.map(msg => 
              msg.id === data.message_id ? { ...msg, is_delivered: true } : msg
            ));
            break;

          case 'message_seen':
            setMessages((prev) => prev.map(msg => 
              msg.id === data.message_id ? { ...msg, is_seen: true } : msg
            ));
            break;

          case 'user_online':
            if (data.user_id === activeContact) setIsOnline(true);
            break;

          case 'user_offline':
            if (data.user_id === activeContact) setIsOnline(false);
            break;

          case 'typing':
            if (data.sender_id === activeContact) {
              setIsTyping(true);
              clearTimeout(typingTimeoutRef.current);
              typingTimeoutRef.current = setTimeout(() => setIsTyping(false), 2000);
            }
            break;

          default:
            break;
        }
      } catch (e) {
        console.error('Error parsing message', e);
      }
    };

    socket.onclose = () => {
      console.log('WebSocket Disconnected');
      clearInterval(pingInterval);
    };

    setWs(socket);

    return () => {
      clearInterval(pingInterval);
      socket.close();
    };
  }, [navigate, activeContact]);

  const loadHistory = async (username) => {
    try {
      const response = await getChatHistory(username);
      setMessages(response.messages);
      setActiveContact(response.contact_id);
      setActiveUsername(response.contact_username);
      setIsOnline(false); // Can be improved by adding HTTP endpoint to check initial status
    } catch (err) {
      console.error('Failed to load history', err);
    }
  };

  const handleStartChat = (e) => {
    e.preventDefault();
    if (contactUsernameInput) {
      loadHistory(contactUsernameInput);
    }
  };

  const handleTyping = (e) => {
    setNewMessage(e.target.value);
    if (ws && ws.readyState === WebSocket.OPEN && activeContact) {
      ws.send(JSON.stringify({
        event: "typing",
        data: { receiver_id: activeContact }
      }));
    }
  };

  const handleSendMessage = (e) => {
    e.preventDefault();
    if (!newMessage.trim() || !activeContact || !ws) return;

    ws.send(JSON.stringify({
      event: "send_message",
      data: {
        receiver_id: activeContact,
        message: newMessage
      }
    }));
    
    setNewMessage('');
  };

  const handleLogout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('refresh_token');
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
            placeholder="Username (e.g. bob)"
            value={contactUsernameInput}
            onChange={(e) => setContactUsernameInput(e.target.value)}
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
            <Typography variant="body2" color="text.secondary">@{activeUsername}</Typography>
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
            <Box sx={{ p: 2, borderBottom: '1px solid var(--glass-border)', display: 'flex', alignItems: 'center', gap: 2 }}>
              <Badge color="success" variant="dot" invisible={!isOnline}>
                <Avatar sx={{ bgcolor: 'var(--primary)' }}>{activeUsername ? activeUsername[0].toUpperCase() : 'U'}</Avatar>
              </Badge>
              <Box>
                <Typography variant="h6">{activeUsername}</Typography>
                {isOnline && <Typography variant="caption" color="success.main">Online</Typography>}
              </Box>
            </Box>

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
                  const isMine = msg.sender_id !== activeContact && msg.sender_id !== 0;
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
                        p: 1.5,
                        px: 2.5,
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
                        
                        {/* Status Ticks for My Messages */}
                        {isMine && (
                          <Box sx={{ display: 'flex', justifyContent: 'flex-end', mt: 0.5 }}>
                            {msg.is_seen ? (
                              <DoneAll sx={{ fontSize: 16, color: '#4facfe' }} /> // Blue ticks for seen
                            ) : msg.is_delivered ? (
                              <DoneAll sx={{ fontSize: 16, color: 'rgba(255,255,255,0.7)' }} /> // Grey ticks for delivered
                            ) : (
                              <Check sx={{ fontSize: 16, color: 'rgba(255,255,255,0.7)' }} /> // Single tick for sent
                            )}
                          </Box>
                        )}
                      </Box>
                    </motion.div>
                  );
                })}
              </AnimatePresence>
              
              {/* Typing Indicator */}
              <AnimatePresence>
                {isTyping && (
                  <motion.div
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, scale: 0.8 }}
                  >
                    <Box sx={{ 
                      display: 'flex', 
                      gap: 0.5, 
                      p: 2, 
                      maxWidth: 'fit-content',
                      background: 'var(--bg-input)',
                      borderRadius: 4,
                      borderBottomLeftRadius: 4
                    }}>
                      <motion.div animate={{ y: [0, -5, 0] }} transition={{ repeat: Infinity, duration: 0.6, delay: 0 }} style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--primary)' }} />
                      <motion.div animate={{ y: [0, -5, 0] }} transition={{ repeat: Infinity, duration: 0.6, delay: 0.2 }} style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--primary)' }} />
                      <motion.div animate={{ y: [0, -5, 0] }} transition={{ repeat: Infinity, duration: 0.6, delay: 0.4 }} style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--primary)' }} />
                    </Box>
                  </motion.div>
                )}
              </AnimatePresence>
              
              <div ref={messagesEndRef} />
            </Box>

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
                onChange={handleTyping}
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
              animate={{ scale: [1, 1.1, 1], opacity: [0.5, 1, 0.5] }}
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
