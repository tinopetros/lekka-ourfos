import { FileText } from 'lucide-react';
import type { Answer } from '@/lib/api/types';
import { LINK } from '@/lib/styles';

// Opens as its emails link it: Drive's in Drive, ours streamed by the API behind IAP, through a page that says it's
// on its way
export function FileLink({ file }: { file: Answer['files'][number] }) {
  return (
    <a
      href={file.url.replace(/^\/api\/files/, '/files')}
      target="_blank"
      rel="noreferrer"
      className={`inline-flex items-center gap-1 ${LINK}`}
    >
      <FileText className="size-3.5" /> {file.name}
    </a>
  );
}
