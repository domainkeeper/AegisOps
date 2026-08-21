import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import './styles/theme.css';

const root = document.getElementById('root');
if (!root) throw new Error('Root element not found');

createRoot(root).render(
  <StrictMode>
    <div>AegisOps</div>
  </StrictMode>,
);