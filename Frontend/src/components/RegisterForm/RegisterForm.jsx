import React, { useState } from "react";
import { FaUser, FaLock } from "react-icons/fa";
import { useNavigate, Link } from "react-router-dom";

const RegisterForm = () => {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");

  const navigate = useNavigate();

  const handleRegister = async (e) => {
    e.preventDefault();
    setError("");

    try {
      const response = await fetch("http://localhost:8080/register", {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({ username, password }),
        mode: "cors",
        credentials: "omit"
      });

      const data = await response.json();

      if (response.ok) {
        console.log("✅ Registered successfully:", data);
        navigate("/");
      } else {
        setError(data.error || "❌ Registration failed");
      }
    } catch (err) {
      setError("❌ Server connection error");
      console.error(err);
    }
  };

  return (
    <div className="register-layout">
      <div className="register-wrapper">
        <form onSubmit={handleRegister}>
          <h1>Register</h1>
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
          <button type="submit">Register</button>
          <div className="remember-forgot" style={{ marginTop: "10px" }}>
            <span>
              Already have an account? <Link to="/">Login</Link>
            </span>
          </div>
        </form>
      </div>
    </div>
  );
};

export default RegisterForm;
