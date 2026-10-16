import React, { ButtonHTMLAttributes, forwardRef } from 'react';

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger';
  size?: 'sm' | 'md' | 'lg';
  loading?: boolean;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ variant = 'secondary', size = 'md', loading = false, disabled, children, className = '', type = 'button', ...props }, ref) => {
    const variantClass = variant === 'primary' ? 'btn-primary' : variant === 'danger' ? 'btn-danger' : variant === 'ghost' ? 'btn-ghost' : 'btn-secondary';
    const sizeClass = size === 'sm' ? 'btn-sm' : size === 'lg' ? 'btn-lg' : 'btn-md';

    return (
      <button
        ref={ref}
        type={type}
        disabled={disabled || loading}
        className={`btn ${variantClass} ${sizeClass} ${loading ? 'is-loading' : ''} ${className}`}
        {...props}
      >
        {loading && <span className="btn-spinner" aria-hidden="true" />}
        <span className="btn-label">{children}</span>
      </button>
    );
  }
);

Button.displayName = 'Button';
