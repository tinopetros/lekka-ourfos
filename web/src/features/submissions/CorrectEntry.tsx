import { Loader2, PencilLine } from 'lucide-react';
import { useRef, useState } from 'react';
import { Tip } from '@/components/Tip';
import { ConfirmContent } from '@/components/ConfirmContent';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogClose,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { accountLabel as label } from '@/lib/format';
import type { JournalEntry } from '@/lib/api/types';
import { type useCorrection } from './api';
import { EntryLines } from './EntryLines';
import { cents, row, useEntryLines } from './lines';

export const CORRECT_TIP =
  'Posts a reversal to Mifos, then the corrected lines you set here, on the same date. The corrected entry is then the live one, and the requisition’s thread is told why.';

// Corrects a requisition's live entry: its mirror, then the lines set here. They start as the entry's own, and it
// posts only when each has an account Mifos lets it post to and debits equal credits
export function CorrectEntry({ e, correction }: { e: JournalEntry; correction: ReturnType<typeof useCorrection> }) {
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState('');
  // Once a correction's been tried, what's still in its way is said: the reason beside its box, the first of the rest
  // by the button
  const [tried, setTried] = useState(false);
  const why = useRef<HTMLTextAreaElement>(null);
  const editor = useEntryLines(e.tenant, open);
  const correcting = correction.isPending && !!correction.variables.transaction_id && !!correction.variables.lines;

  const same =
    JSON.stringify(editor.picked.map((x) => [x.side, x.to?.glId, cents(x.value)])) ===
    JSON.stringify(e.lines.map((x) => [x.type, x.glId, cents(x.amount)]));
  const missing = !reason.trim();
  const problems = [
    ...editor.problems,
    // A reason alone corrects nothing
    ...(same ? ['The journal entry hasn’t been corrected yet: change at least one line'] : []),
  ];

  return (
    <>
      <Tip label={CORRECT_TIP} delay={300}>
        <span>
          <Button
            variant="outline"
            size="sm"
            disabled={correction.isPending}
            onClick={() => {
              editor.setLines(
                e.lines.map((x) =>
                  row({
                    side: x.type ?? 'DEBIT',
                    glId: x.glId ?? undefined,
                    shown: label(x),
                    amount: String(x.amount),
                  }),
                ),
              );
              setReason('');
              setTried(false);
              setOpen(true);
            }}
          >
            {correcting ? <Loader2 className="animate-spin" /> : <PencilLine />}
            {correcting ? 'Correcting…' : 'Correct journal entry'}
          </Button>
        </span>
      </Tip>
      <Dialog open={open} onOpenChange={setOpen}>
        <ConfirmContent className="gap-6 sm:max-w-3xl">
          <DialogHeader>
            <DialogTitle>Correct journal entry</DialogTitle>
            <DialogDescription>
              Transaction <span className="text-foreground">{e.transaction_id}</span> will be reversed in Mifos, then
              these lines posted on the same date{e.tenant === 'demo' ? ', in demo' : ''}. Pick each line&apos;s account
              from Mifos&apos;s, by its name or GL code: only those that take manual entries are listed.
            </DialogDescription>
          </DialogHeader>
          <EntryLines editor={editor} currency={e.currency} />
          <div className="space-y-2">
            <Label htmlFor="correct-reason">
              Why it&apos;s corrected <span className="text-destructive">*</span>
            </Label>
            <Textarea
              id="correct-reason"
              ref={why}
              rows={3}
              placeholder="e.g. Booked to the wrong expense account"
              aria-invalid={tried && missing}
              value={reason}
              onChange={(ev) => {
                setReason(ev.target.value);
              }}
            />
            {tried && missing && (
              <p role="alert" className="text-sm text-destructive">
                A reason is needed to correct it.
              </p>
            )}
          </div>
          {tried && problems.length > 0 && (
            <p role="alert" className="text-sm text-destructive">
              {problems[0]}.
            </p>
          )}
          <DialogFooter>
            <DialogClose asChild>
              <Button variant="outline">Cancel</Button>
            </DialogClose>
            <Button
              disabled={correction.isPending}
              onClick={() => {
                if (problems.length || missing) {
                  setTried(true);
                  if (missing) why.current?.focus();
                  return;
                }
                setOpen(false);
                correction.mutate({ transaction_id: e.transaction_id, reason: reason.trim(), lines: editor.sides() });
              }}
            >
              Correct journal entry
            </Button>
          </DialogFooter>
        </ConfirmContent>
      </Dialog>
    </>
  );
}
