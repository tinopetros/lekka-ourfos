import type { ComponentProps } from 'react';
import { DialogContent } from '@/components/ui/dialog';

// A dialog left only by its own buttons: no ×, and neither a click outside nor Escape closes it, so a slip loses nothing
export function ConfirmContent(props: ComponentProps<typeof DialogContent>) {
  return (
    <DialogContent
      showCloseButton={false}
      onInteractOutside={(e) => {
        e.preventDefault();
      }}
      onEscapeKeyDown={(e) => {
        e.preventDefault();
      }}
      {...props}
    />
  );
}
