import React, { useState } from 'react';
import { FaUser, FaLock } from "react-icons/fa";
import { useNavigate, Link } from 'react-router-dom';

const LoginForm = () => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');

  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');

    try {
      const response = await fetch('http://localhost:8080/login', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ username, password }),
        mode: 'cors',
        credentials: 'omit'
      });

      const data = await response.json();

      if (response.ok) {
        localStorage.setItem('user', JSON.stringify({
          username,
          password,
          plants: data.plants
        }));
        console.log('✅ Successful Login:', data);

        navigate('/dashboard');
        window.location.reload();
      } else {
        setError(data.error || '❌ Error while logging in');
      }
    } catch (err) {
      setError('❌ Server Connection Error');
      console.log('Error:', err);
    }
  };

  return (
    <div className="login-layout">
      <div className="login-wrapper">
        <form onSubmit={handleSubmit}>
          <h1>Login</h1>
          <div className="input-box">
            <input
              type="text"
              placeholder="Username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
            />
            <FaUser className="icon" />
          </div>
          <div className="input-box">
            <input
              type="password"
              placeholder="Password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
            <FaLock className="icon" />
          </div>
          {error && <div className="error">{error}</div>}
          <button type="submit">Login</button>
          <div className="remember-forgot" style={{ marginTop: "10px" }}>
            <span>
              Don't have an account? <Link to="/register">Register</Link>
            </span>
          </div>
        </form>
      </div>
    </div>
  );
};

export default LoginForm;

