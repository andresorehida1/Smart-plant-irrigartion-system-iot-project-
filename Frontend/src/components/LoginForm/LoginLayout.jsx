// src/components/LoginForm/LoginLayout.jsx
import React from "react";
import "./LoginForm.css";

const LoginLayout = ({ children }) => {
  return (
    <div className="login-layout">
      {children}
    </div>
  );
};

export default LoginLayout; 