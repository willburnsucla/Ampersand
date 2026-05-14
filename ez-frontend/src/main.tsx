import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './app/App';

// import whichever global styles your project needs
import './styles/index.css';
import './styles/theme.css';
import './styles/tailwind.css';
import './styles/fonts.css';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);