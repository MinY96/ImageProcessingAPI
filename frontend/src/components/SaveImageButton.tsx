import { Button } from './ui';

type WritableFile = {
  write: (data: Blob) => Promise<void>;
  close: () => Promise<void>;
};
type SaveFileHandle = { createWritable: () => Promise<WritableFile> };
type SavePickerWindow = Window & {
  showSaveFilePicker?: (options: {
    suggestedName: string;
    types: Array<{ description: string; accept: Record<string, string[]> }>;
  }) => Promise<SaveFileHandle>;
};

function extensionFor(type: string): string {
  if (type.includes('jpeg')) return 'jpg';
  if (type.includes('webp')) return 'webp';
  return 'png';
}

export function SaveImageButton({
  source,
  fileName = 'image',
  disabled = false,
}: {
  source?: Blob | string | null;
  fileName?: string;
  disabled?: boolean;
}) {
  const save = async () => {
    if (!source) return;
    try {
      const blob = source instanceof Blob ? source : await (await fetch(source)).blob();
      const extension = extensionFor(blob.type);
      const suggestedName = fileName.toLowerCase().endsWith(`.${extension}`)
        ? fileName
        : `${fileName}.${extension}`;
      const picker = (window as SavePickerWindow).showSaveFilePicker;
      if (picker) {
        const handle = await picker.call(window, {
          suggestedName,
          types: [{
            description: 'Image',
            accept: {
              'image/png': ['.png'],
              'image/jpeg': ['.jpg', '.jpeg'],
              'image/webp': ['.webp'],
            },
          }],
        });
        const writable = await handle.createWritable();
        await writable.write(blob);
        await writable.close();
        return;
      }
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = suggestedName;
      anchor.click();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (error) {
      if (error instanceof DOMException && error.name === 'AbortError') return;
      console.error('Image save failed', error);
    }
  };

  return <Button variant="ghost" disabled={disabled || !source} onClick={() => void save()} title="Save image to a selected location">Save</Button>;
}
