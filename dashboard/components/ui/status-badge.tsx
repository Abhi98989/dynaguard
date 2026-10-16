import React from 'react';

export type StatusType =
  | 'passed'
  | 'failed'
  | 'running'
  | 'incomplete'
  | 'cancelled'
  | 'verified_fixed'
  | 'open'
  | 'ready_for_release'
  | 'rejected'
  | 'not_evaluated'
  | 'critical'
  | 'high'
  | 'medium'
  | 'low'
  | 'info'
  | 'checked'
  | string;

export interface StatusBadgeProps {
  status: StatusType;
  label?: string;
  size?: 'sm' | 'md';
  className?: string;
}

export function StatusBadge({ status, label, size = 'md', className = '' }: StatusBadgeProps) {
  const normalized = (status || '').toLowerCase().replace(/[\s-]/g, '_');

  let variant = 'default';
  if (['passed', 'verified_fixed', 'ready_for_release', 'checked', 'low', 'info'].includes(normalized)) {
    variant = 'success';
  } else if (['failed', 'rejected', 'open', 'critical', 'high'].includes(normalized)) {
    variant = 'danger';
  } else if (['running'].includes(normalized)) {
    variant = 'running';
  } else if (['incomplete', 'cancelled', 'not_evaluated', 'medium'].includes(normalized)) {
    variant = 'warning';
  }

  const displayLabel = label || status.replace(/_/g, ' ');

  return (
    <span className={`badge badge-${variant} badge-${size} ${normalized} ${className}`}>
      {variant === 'running' && <span className="badge-pulse" aria-hidden="true" />}
      {displayLabel}
    </span>
  );
}
