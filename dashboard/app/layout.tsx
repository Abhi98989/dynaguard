import type { Metadata } from 'next';
import './style.css';
import { ToastProvider } from './toast';

export const metadata: Metadata = {title: 'DynaGuard · Local validation', description: 'Internal security validation for Dynamatrix'};

export default function Layout({children}: Readonly<{children: React.ReactNode}>) {
  return (
    <html lang="en">
      <body>
        <ToastProvider>
          {children}
        </ToastProvider>
      </body>
    </html>
  );
}
