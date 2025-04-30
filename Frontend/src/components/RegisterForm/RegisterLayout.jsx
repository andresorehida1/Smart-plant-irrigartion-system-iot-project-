import React from "react";
import "../RegisterForm/RegisterForm.css";

const RegisterLayout = ({ children }) => {
  return (
    <div className="register-layout">
      {children}
    </div>
  );
};

export default RegisterLayout;