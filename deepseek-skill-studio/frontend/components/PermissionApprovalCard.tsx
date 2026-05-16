'use client';

interface Props {
  permission: string;
  context: string;
  onApprove: (duration: string) => void;
  onDeny: () => void;
  visible: boolean;
}

export default function PermissionApprovalCard({
  permission,
  context,
  onApprove,
  onDeny,
  visible,
}: Props) {
  if (!visible) return null;

  return (
    <div className="modal-overlay" role="dialog" aria-modal="true" aria-label="Permission request">
      <div className="modal confirm-modal" style={{ maxWidth: 440 }}>
        {/* Header */}
        <div className="modal-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <span style={{ fontSize: 22 }}>🔐</span>
            <h2 style={{ margin: 0, fontSize: 16 }}>Permission Request</h2>
          </div>
        </div>

        {/* Body */}
        <div className="modal-body" style={{ gap: 16 }}>
          {/* Permission name */}
          <div className="builder">
            <label>Requested Permission</label>
            <p
              style={{
                margin: '6px 0 0',
                fontWeight: 700,
                fontSize: 15,
                color: 'var(--text)',
                fontFamily: '"Fira Code", Consolas, monospace',
              }}
            >
              {permission}
            </p>
          </div>

          {/* Context */}
          {context && (
            <div className="builder">
              <label>Context</label>
              <p className="muted" style={{ margin: '6px 0 0', fontSize: 14, lineHeight: 1.5 }}>
                {context}
              </p>
            </div>
          )}

          {/* Explanation */}
          <p className="muted small" style={{ margin: 0 }}>
            An agent or tool is requesting this permission. Choose how long to allow it, or deny the request.
          </p>
        </div>

        {/* Footer: approve options */}
        <div className="modal-footer" style={{ flexDirection: 'column', gap: 8 }}>
          <div style={{ display: 'flex', gap: 8, width: '100%' }}>
            <button
              className="secondary"
              style={{ flex: 1, padding: '10px 12px', fontSize: 13 }}
              onClick={() => onApprove('once')}
            >
              Allow Once
            </button>
            <button
              className="secondary"
              style={{ flex: 1, padding: '10px 12px', fontSize: 13 }}
              onClick={() => onApprove('session')}
            >
              Allow for Session
            </button>
            <button
              className="primary"
              style={{ flex: 1, padding: '10px 12px', fontSize: 13 }}
              onClick={() => onApprove('always')}
            >
              Always Allow
            </button>
          </div>
          <button
            className="secondary"
            style={{
              width: '100%',
              padding: '10px 12px',
              fontSize: 13,
              color: 'var(--red)',
              borderColor: 'var(--red-border)',
            }}
            onClick={onDeny}
          >
            ✗ Deny
          </button>
        </div>
      </div>
    </div>
  );
}
