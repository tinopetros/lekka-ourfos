import { Loader2, Undo2 } from 'lucide-react';
import { useRef, useState } from 'react';
import { Tip } from '@/components/Tip';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import type { useCorrection } from './api';

export const REVERSE_TIP =
  'Posts a reversal to Mifos: the same lines with debits and credits swapped, on the same date. Nothing is left live, and the requisition’s thread is told why.';

// Undoes a requisition's live entry, once you've said why and that a mirror entry will be posted. You stay on the
// page, and it shows the entry reversed when it is
export function ReverseEntry({
  transaction,
  correction,
}: {
  transaction: string;
  correction: ReturnType<typeof useCorrection>;
}) {
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState('');
  // Said once a reversal's been tried without a reason
  const [tried, setTried] = useState(false);
  const why = useRef<HTMLTextAreaElement>(null);
  const missing = !reason.trim();
  const reversing = correction.isPending && !correction.variables.lines;
  return (
    <>
      <Tip label={REVERSE_TIP} delay={300}>
        {/* A disabled button hears no hover: its wrapper does */}
        <span>
          <Button
            variant="outline"
            size="sm"
            disabled={correction.isPending}
            onClick={() => {
              setTried(false);
              setOpen(true);
            }}
          >
            {reversing ? <Loader2 className="animate-spin" /> : <Undo2 />}
            {reversing ? 'Reversing…' : 'Reverse journal entry'}
          </Button>
        </span>
      </Tip>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Reverse journal entry?</DialogTitle>
            <DialogDescription>
              A reversal entry will be posted to Mifos for transaction{' '}
              <span className="text-foreground">{transaction}</span>: the same lines, debits and credits swapped, on the
              same date, so the books balance. The requisition is then left with nothing live in Mifos, and its thread
              is told why.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-2">
            <Label htmlFor="reverse-reason">
              Why it&apos;s reversed <span className="text-destructive">*</span>
            </Label>
            <Textarea
              id="reverse-reason"
              ref={why}
              rows={3}
              placeholder="e.g. Posted twice"
              aria-invalid={tried && missing}
              value={reason}
              onChange={(e) => {
                setReason(e.target.value);
              }}
            />
            {tried && missing && (
              <p role="alert" className="text-sm text-destructive">
                A reason is needed to reverse it.
              </p>
            )}
          </div>
          <DialogFooter>
            <DialogClose asChild>
              <Button variant="outline">Cancel</Button>
            </DialogClose>
            <Button
              variant="destructive"
              disabled={correction.isPending}
              onClick={() => {
                if (missing) {
                  setTried(true);
                  why.current?.focus();
                  return;
                }
                setOpen(false);
                correction.mutate({ transaction_id: transaction, reason: reason.trim() });
              }}
            >
              Reverse journal entry
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
