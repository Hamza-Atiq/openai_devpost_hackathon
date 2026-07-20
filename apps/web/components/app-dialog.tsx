"use client";

import { type ReactNode, useEffect, useRef } from "react";

type AppDialogProps = {
  labelledBy: string;
  onClose: () => void;
  children: ReactNode;
  closeDisabled?: boolean;
};

const focusable = 'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

export function AppDialog({ labelledBy, onClose, children, closeDisabled = false }: AppDialogProps) {
  const dialogRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    triggerRef.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const isolated: HTMLElement[] = [];
    let node: HTMLElement | null = dialog;
    while (node?.parentElement) {
      for (const sibling of Array.from(node.parentElement.children)) {
        if (sibling !== node && sibling instanceof HTMLElement && !sibling.inert) {
          sibling.inert = true;
          isolated.push(sibling);
        }
      }
      node = node.parentElement;
    }
    (dialog.querySelector(focusable) as HTMLElement | null)?.focus();

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape" && !closeDisabled) {
        event.preventDefault();
        onClose();
        return;
      }
      if (event.key !== "Tab") return;
      const items = Array.from(dialog!.querySelectorAll<HTMLElement>(focusable));
      if (!items.length) return;
      const first = items[0];
      const last = items[items.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    }
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      isolated.forEach((element) => { element.inert = false; });
      triggerRef.current?.focus();
    };
  }, [closeDisabled, onClose]);

  return <div className="app-dialog-backdrop"><div ref={dialogRef} className="approval-dialog" role="dialog" aria-modal="true" aria-labelledby={labelledBy}>{children}</div></div>;
}
