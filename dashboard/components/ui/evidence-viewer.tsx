'use client';

import React, { useState } from 'react';
import { Button } from './button';

export interface EvidenceViewerProps {
  content: unknown;
  sha256?: string;
  summaryTitle?: string;
  defaultOpen?: boolean;
  className?: string;
}

export function EvidenceViewer({
  content,
  sha256,
  summaryTitle = 'Masked evidence and integrity hash',
  defaultOpen = false,
  className = ''
}: EvidenceViewerProps) {
  const [copied, setCopied] = useState(false);
  const formatted = typeof content === 'string' ? content : JSON.stringify(content, null, 2);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(formatted);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // ignore clipboard error
    }
  };

  return (
    <details className={`evidence-viewer ${className}`} open={defaultOpen}>
      <summary className="evidence-summary">
        <span>{summaryTitle}</span>
        {sha256 && <span className="evidence-summary-tag">SHA-256 verified</span>}
      </summary>
      <div className="evidence-content-wrapper">
        <div className="evidence-toolbar">
          <span className="evidence-meta">Masked synthetic output · private keys redacted</span>
          <Button size="sm" variant="ghost" onClick={copy} type="button">
            {copied ? '✓ Copied' : 'Copy raw evidence'}
          </Button>
        </div>
        <pre className="evidence-pre">
          <code>{formatted}</code>
        </pre>
        {sha256 && (
          <div className="evidence-hash">
            <span className="hash-label">Integrity:</span>
            <code className="hash-value">SHA-256 {sha256}</code>
          </div>
        )}
      </div>
    </details>
  );
}
