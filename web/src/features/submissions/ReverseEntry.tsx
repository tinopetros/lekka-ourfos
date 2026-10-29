import { Loader2, Undo2 } from 'lucide-react';
import { useState } from 'react';
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
import { useReverse } from './api';

// Undoes a requisition's live entry, once you've said why and that a mirror entry will be posted. You stay on the
// page, and it shows the entry reversed when it is
export function ReverseEntry({ id, transaction }: { id: string; transaction: string }) {
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState('');
  const reverse = useReverse(id);
  return (
    <>
      <Button
        variant="outline"
        size="sm"
        disabled={reverse.isPending}
        onClick={() => {
          setOpen(true);
        }}
      >
        {reverse.isPending ? <Loader2 className="animate-spin" /> : <Undo2 />}
        {reverse.isPending ? 'Reversing…' : 'Reverse journal entry'}
      </Button>
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
            <Label htmlFor="reason">Why it&apos;s reversed</Label>
            <Textarea
              id="reason"
              rows={3}
              value={reason}
              onChange={(e) => {
                setReason(e.target.value);
              }}
            />
          </div>
          <DialogFooter>
            <DialogClose asChild>
              <Button variant="outline">Cancel</Button>
            </DialogClose>
            <Button
              variant="destructive"
              disabled={!reason.trim()}
              onClick={() => {
                setOpen(false);
                reverse.mutate({ transaction_id: transaction, reason: reason.trim() });
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
