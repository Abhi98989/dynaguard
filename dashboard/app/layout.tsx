import type { Metadata, Viewport } from 'next';
import './style.css';
import { ToastProvider } from './toast';

export const metadata: Metadata = {
  title: 'DynaGuard · Security Validation & QA Platform',
  description: 'Evidence before conclusions. Internal security validation and QA workspace.'
};

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
};

export default function Layout({ children }: Readonly<{ children: React.ReactNode }>) {
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
