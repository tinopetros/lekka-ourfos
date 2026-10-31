import { Check, CheckCheck, Loader2, MessageSquare, Paperclip, X } from 'lucide-react';
import { useRef, useState, type ComponentProps } from 'react';
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
import type { ActionKind } from '@/lib/api/types';
import type { useAction } from './actions';

type Variant = ComponentProps<typeof Button>['variant'];

// Each action's button, dialog and comment. All but an approval say why
const KINDS: Record<
  ActionKind,
  { label: string; icon: typeof Check; variant: Variant; asks: string; placeholder: string; needed: boolean }
> = {
  done: {
    label: 'Mark as done',
    icon: CheckCheck,
    variant: 'success',
    asks: 'How it was finished',
    placeholder: 'e.g. Posted the corrected lines in Mifos by hand',
    needed: true,
  },
  approve: {
    label: 'Approve',
    icon: Check,
    variant: 'success',
    asks: 'Comment',
    placeholder: 'Anything to add, if you like',
    needed: false,
  },
  disapprove: {
    label: 'Disapprove',
    icon: X,
    variant: 'destructive',
    asks: 'Why it’s disapproved',
    placeholder: 'e.g. Not a business expense',
    needed: true,
  },
  comment: {
    label: 'Comment',
    icon: MessageSquare,
    variant: 'outline',
    asks: 'Comment',
    placeholder: 'e.g. Checked the client’s statements',
    needed: true,
  },
};

/** One action on a submission, from its page's top row: a dialog that says what will happen, a comment, any files,
 * and the button that takes it. The page stays, and shows it once it's kept */
export function ActionButton({
  kind,
  noun,
  reverses,
  action,
}: {
  kind: ActionKind;
  noun: string;
  // A requisition's live entry, which disapproving it reverses
  reverses?: string | null;
  action: ReturnType<typeof useAction>;
}) {
  const k = KINDS[kind];
  const [open, setOpen] = useState(false);
  const [comment, setComment] = useState('');
  const [files, setFiles] = useState<File[]>([]);
  const [tried, setTried] = useState(false);
  const why = useRef<HTMLTextAreaElement>(null);
  const missing = k.needed && !comment.trim();
  const busy = action.isPending && action.variables.kind === kind;
  const Icon = k.icon;
  const what: Record<ActionKind, string> = {
    done: `This ${noun} will be marked done, and its thread told how.`,
    approve: `This ${noun} will be approved, and its thread told.`,
    disapprove: reverses
      ? `Transaction ${reverses} will be reversed in Mifos first: the same lines, debits and credits swapped, on the same date. Then this ${noun} is disapproved, and its thread told why.`
      : `This ${noun} will be disapproved, and its thread told why.`,
    comment: `Your comment goes on this ${noun}'s history and to its thread.`,
  };
  return (
    <>
      <Button
        variant={k.variant}
        size="sm"
        disabled={action.isPending}
        onClick={() => {
          setComment('');
          setFiles([]);
          setTried(false);
          setOpen(true);
        }}
      >
        {busy ? <Loader2 className="animate-spin" /> : <Icon />}
        {k.label}
      </Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <ConfirmContent>
          <DialogHeader>
            <DialogTitle>{k.label}?</DialogTitle>
            <DialogDescription>{what[kind]}</DialogDescription>
          </DialogHeader>
          <div className="space-y-2">
            <Label htmlFor={`action-${kind}`}>
              {k.asks} {k.needed && <span className="text-destructive">*</span>}
            </Label>
            <Textarea
              id={`action-${kind}`}
              ref={why}
              rows={3}
              placeholder={k.placeholder}
              aria-invalid={tried && missing}
              value={comment}
              onChange={(e) => {
                setComment(e.target.value);
              }}
            />
            {tried && missing && (
              <p role="alert" className="text-sm text-destructive">
                A comment is needed to {k.label.toLowerCase()}.
              </p>
            )}
          </div>
          <div className="space-y-2">
            <Label htmlFor={`action-${kind}-files`}>
              <Paperclip className="size-4" /> Files
            </Label>
            <Input
              id={`action-${kind}-files`}
              type="file"
              multiple
              onChange={(e) => {
                setFiles(Array.from(e.target.files ?? []));
              }}
            />
            {files.length > 0 && (
              <p className="text-xs text-muted-foreground">
                {files.map((f) => f.name).join(', ')}: linked in the email by Ourfos, behind its sign-in
              </p>
            )}
          </div>
          <DialogFooter>
            <DialogClose asChild>
              <Button variant="outline">Cancel</Button>
            </DialogClose>
            <Button
              variant={k.variant === 'outline' ? 'default' : k.variant}
              disabled={action.isPending}
              onClick={() => {
                if (missing) {
                  setTried(true);
                  why.current?.focus();
                  return;
                }
                setOpen(false);
                action.mutate({ kind, comment: comment.trim(), files });
              }}
            >
              {k.label}
            </Button>
          </DialogFooter>
        </ConfirmContent>
      </Dialog>
    </>
  );
}
