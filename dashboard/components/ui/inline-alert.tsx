import React from 'react';

export interface InlineAlertProps {
  variant?: 'error' | 'warning' | 'info' | 'success';
  title?: string;
  children: React.ReactNode;
  className?: string;
}

export function InlineAlert({ variant = 'info', title, children, className = '' }: InlineAlertProps) {
  return (
    <div className={`inline-alert alert-${variant} ${variant === 'error' ? 'error' : ''} ${className}`} role="alert">
      <div className="alert-body">
        {title && <strong className="alert-title">{title}</strong>}
        <div className="alert-content">{children}</div>
      </div>
    </div>
  );
}
