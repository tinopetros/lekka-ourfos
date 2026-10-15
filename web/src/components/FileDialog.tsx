import { ExternalLink, FileText } from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import type { Answer } from '@/lib/api/types';

type File = Answer['files'][number];

// Drive's own preview, which shows only what your Google account can open; ours, streamed by the API behind IAP
function urls(file: File): { view: string; open: string } {
  if (file.drive_id)
    return {
      view: `https://drive.google.com/file/d/${encodeURIComponent(file.drive_id)}/preview`,
      open: `https://drive.google.com/open?id=${encodeURIComponent(file.drive_id)}`,
    };
  const ours = `/api/files?${new URLSearchParams({ ref: file.ref ?? '' }).toString()}`;
  return { view: ours, open: ours };
}

export function FileDialog({ file }: { file: File }) {
  const { view, open } = urls(file);
  return (
    <Dialog>
      <DialogTrigger className="inline-flex items-center gap-1 underline underline-offset-2">
        <FileText className="size-3.5" /> {file.name}
      </DialogTrigger>
      <DialogContent className="flex h-[85dvh] max-w-[90vw] flex-col sm:max-w-[90vw]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            {file.name}
            <a
              href={open}
              target="_blank"
              rel="noreferrer"
              className="text-muted-foreground"
              aria-label="Open in a new tab"
            >
              <ExternalLink className="size-4" />
            </a>
          </DialogTitle>
          <DialogDescription>{file.drive_id ? 'From Google Drive' : 'From our attachments'}</DialogDescription>
        </DialogHeader>
        <iframe src={view} title={file.name} className="min-h-0 w-full flex-1 rounded-md border bg-muted" />
      </DialogContent>
    </Dialog>
  );
}
