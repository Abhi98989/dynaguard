import React from 'react';

export interface FieldProps {
  id?: string;
  label: string;
  helpText?: string;
  error?: string;
  required?: boolean;
  className?: string;
  children: React.ReactNode;
}

export function Field({ id, label, helpText, error, required, className = '', children }: FieldProps) {
  return (
    <div className={`form-field ${error ? 'has-error' : ''} ${className}`}>
      <label htmlFor={id} className="field-label">
        <span>{label}</span>
        {required && <span className="field-required" aria-hidden="true">*</span>}
      </label>
      <div className="field-control">{children}</div>
      {helpText && !error && <p className="field-help" id={id ? `${id}-help` : undefined}>{helpText}</p>}
      {error && <p className="field-error" id={id ? `${id}-error` : undefined} role="alert">{error}</p>}
    </div>
  );
}
