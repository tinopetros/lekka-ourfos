import { FilePlus2, Loader2 } from 'lucide-react';
import { useState } from 'react';
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
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import type { components } from '@/lib/api/schema';
import { TONE } from '@/lib/styles';
import { type useCorrection } from './api';
import { EntryLines } from './EntryLines';
import { row, useEntryLines } from './lines';

type Posting = components['schemas']['Posting'];

export const POST_TIP =
  'Posts the lines you set here to Mifos, filed as Lekkai would have filed them. They’re then the requisition’s live entry, and its thread is told.';

/** Posts a requisition with nothing live: handed over the first time, or reversed with nothing after. The
 * correction's lines with none to start from, filed under what the requisition says, each shown and changeable, and
 * asked for only where it doesn't say. No reason: a handover isn't the poster's doing */
export function PostEntry({ posting, correction }: { posting: Posting; correction: ReturnType<typeof useCorrection> }) {
  const [open, setOpen] = useState(false);
  const [reference, setReference] = useState('');
  const [date, setDate] = useState('');
  const [comments, setComments] = useState('');
  const [tried, setTried] = useState(false);
  const editor = useEntryLines(posting.tenant, open);
  const busy = correction.isPending && !!correction.variables.post;
  const problems = [
    !reference.trim() && 'Give its reference number',
    !date && 'Give its transaction date',
    !comments.trim() && 'Give its comments in Mifos',
    ...editor.problems,
  ].filter((x) => x !== false);

  return (
    <>
      <Tip label={POST_TIP} delay={300}>
        <span>
          <Button
            variant="outline"
            size="sm"
            className={TONE.success}
            disabled={correction.isPending}
            onClick={() => {
              editor.setLines([row({ side: 'DEBIT', amount: '' }), row({ side: 'CREDIT', amount: '' })]);
              setReference(posting.reference ?? '');
              setDate(posting.transaction_date ?? '');
              setComments(posting.comments);
              setTried(false);
              setOpen(true);
            }}
          >
            {busy ? <Loader2 className="animate-spin" /> : <FilePlus2 />}
            {busy ? 'Posting…' : 'Post journal entry'}
          </Button>
        </span>
      </Tip>
      <Dialog open={open} onOpenChange={setOpen}>
        <ConfirmContent className="gap-6 sm:max-w-3xl">
          <DialogHeader>
            <DialogTitle>Post journal entry</DialogTitle>
            <DialogDescription>
              Nothing is live in Mifos for this requisition. These lines will be posted
              {posting.tenant === 'demo' ? ' to demo' : ''}, filed as below, and its thread told. Pick each line&apos;s
              account from Mifos&apos;s, by its name or GL code: only those that take manual entries are listed.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="post-reference">
                Reference number <span className="text-destructive">*</span>
              </Label>
              <Input
                id="post-reference"
                aria-invalid={tried && !reference.trim()}
                value={reference}
                onChange={(ev) => {
                  setReference(ev.target.value);
                }}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="post-date">
                Transaction date <span className="text-destructive">*</span>
              </Label>
              <Input
                id="post-date"
                type="date"
                aria-invalid={tried && !date}
                value={date}
                onChange={(ev) => {
                  setDate(ev.target.value);
                }}
              />
            </div>
          </div>
          <EntryLines editor={editor} currency={null} />
          <div className="space-y-2">
            <Label htmlFor="post-comments">
              Comments in Mifos <span className="text-destructive">*</span>
            </Label>
            <Textarea
              id="post-comments"
              rows={2}
              aria-invalid={tried && !comments.trim()}
              value={comments}
              onChange={(ev) => {
                setComments(ev.target.value);
              }}
            />
            <p className="text-xs text-muted-foreground">
              The workflow run is added when it posts, as Lekkai&apos;s are.
            </p>
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
              variant="success"
              disabled={correction.isPending}
              onClick={() => {
                if (problems.length) {
                  setTried(true);
                  return;
                }
                setOpen(false);
                correction.mutate({
                  lines: editor.sides(),
                  post: { reference: reference.trim(), transaction_date: date, comments: comments.trim() },
                });
              }}
            >
              Post journal entry
            </Button>
          </DialogFooter>
        </ConfirmContent>
      </Dialog>
    </>
  );
}
