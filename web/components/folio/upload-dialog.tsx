"use client";

import { useEffect, useId, useRef, useState } from "react";
import { FileText, LoaderCircle, Plus, TriangleAlert, Upload, X } from "lucide-react";
import { errorMessage, type UploadRequest } from "@/lib/api";
import {
  ACCEPTED_FILE_TYPES,
  MAX_TITLE_LENGTH,
  titleFromFilename,
  validateUpload,
  type UploadErrors,
  type UploadInput,
} from "@/lib/upload";
import { cn } from "@/lib/utils";

type UploadDialogProps = {
  onUpload: (request: UploadRequest) => Promise<void>;
  onClose: () => void;
};

const formatSize = (bytes: number) =>
  bytes < 1024 * 1024
    ? `${Math.max(1, Math.round(bytes / 1024))} KB`
    : `${(bytes / (1024 * 1024)).toFixed(1)} MB`;

/** Rendered only while open, so every opening starts with an empty form. */
export function UploadDialog({ onUpload, onClose }: UploadDialogProps) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const id = useId();
  const [input, setInput] = useState<UploadInput>({
    file: null,
    title: "",
    report_date: "",
    source_url: "",
  });
  const [errors, setErrors] = useState<UploadErrors>({});
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [dragging, setDragging] = useState(false);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (dialog && !dialog.open) dialog.showModal();
  }, []);

  function update<K extends keyof UploadInput>(key: K, value: UploadInput[K]) {
    setInput((current) => ({ ...current, [key]: value }));
    setErrors((current) => ({ ...current, [key]: undefined }));
    setSubmitError(null);
  }

  function chooseFile(file: File | undefined) {
    if (!file) return;
    update("file", file);
    // Suggest a title from the filename, but never overwrite one the user typed.
    setInput((current) =>
      current.title ? current : { ...current, title: titleFromFilename(file.name) },
    );
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    const found = validateUpload(input);
    setErrors(found);
    if (Object.keys(found).length > 0 || !input.file) return;

    setSubmitting(true);
    setSubmitError(null);
    try {
      await onUpload({
        file: input.file,
        title: input.title.trim(),
        report_date: input.report_date,
        source_url: input.source_url.trim() || null,
      });
    } catch (error) {
      setSubmitError(errorMessage(error));
      setSubmitting(false);
    }
  }

  const fieldClass = (invalid: boolean) =>
    cn(
      "w-full rounded-lg border bg-white px-3 py-2.5 text-[13px] text-[#3f5067] outline-none transition-[border-color,box-shadow] placeholder:text-[#a6b0be] focus:border-[#8eafd3] focus:shadow-[0_0_0_3px_#c6d9ee40] disabled:bg-[#f4f5f7]",
      invalid ? "border-[#d9a49a]" : "border-[#d1dae5]",
    );

  return (
    <dialog
      ref={dialogRef}
      aria-labelledby={`${id}-title`}
      onClose={onClose}
      onCancel={(event) => {
        // Don't abandon an upload that is already on its way.
        if (submitting) event.preventDefault();
      }}
      onClick={(event) => {
        if (event.target === dialogRef.current && !submitting) dialogRef.current.close();
      }}
      className="m-auto w-[min(520px,calc(100vw-24px))] max-h-[calc(100dvh-24px)] overflow-y-auto rounded-[17px] border border-white/70 bg-[#fbfbfb] p-0 text-[#3e4856] shadow-[0_25px_80px_#0b162d33] backdrop:bg-[#14202f54] backdrop:backdrop-blur-[6px]"
    >
      <form noValidate onSubmit={submit} className="p-5 sm:p-6">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 id={`${id}-title`} className="text-[20px] font-medium tracking-[-0.03em] text-[#2c333d]">
              Add a dated report
            </h2>
            <p className="mt-1 text-[12.5px] leading-relaxed text-[#8a95a3]">
              Text-based PDF or TXT, up to 10 MB. The report date is when it was
              published, not today.
            </p>
          </div>
          <button
            type="button"
            onClick={() => dialogRef.current?.close()}
            disabled={submitting}
            aria-label="Close"
            className="grid size-8 shrink-0 place-items-center rounded-md text-[#9ca7b4] hover:enabled:bg-[#dde3eb60] hover:enabled:text-[#264b7d]"
          >
            <X size={18} />
          </button>
        </div>

        <div className="mt-5">
          <input
            ref={fileRef}
            id={`${id}-file`}
            type="file"
            accept={ACCEPTED_FILE_TYPES}
            className="sr-only"
            disabled={submitting}
            aria-invalid={!!errors.file}
            aria-describedby={errors.file ? `${id}-file-error` : undefined}
            onChange={(event) => chooseFile(event.target.files?.[0])}
          />
          <label
            htmlFor={`${id}-file`}
            onDragOver={(event) => {
              event.preventDefault();
              setDragging(true);
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={(event) => {
              event.preventDefault();
              setDragging(false);
              if (!submitting) chooseFile(event.dataTransfer.files[0]);
            }}
            className={cn(
              "flex cursor-pointer items-center gap-3.5 rounded-xl border border-dashed p-4 transition-colors",
              dragging
                ? "border-[#6f9be0] bg-[#e6eef8]"
                : errors.file
                  ? "border-[#d9a49a] bg-[#fdf6f4]"
                  : "border-[#b9c7d8] bg-[#f0f4f9] hover:bg-[#e9f0f8]",
              submitting && "cursor-default opacity-70",
            )}
          >
            <span className="relative grid size-11 shrink-0 place-items-center rounded-[9px] border border-[#ccdaec] bg-[#e5edf7] text-[#718fb6]">
              <FileText size={21} strokeWidth={1.5} />
              <span className="absolute -bottom-1 -right-1 grid size-[18px] place-items-center rounded-full bg-white shadow-[0_2px_5px_#00000010]">
                <Plus size={11} />
              </span>
            </span>
            {input.file ? (
              <span className="min-w-0">
                <strong className="block truncate text-[13px] font-medium text-[#3f5067]">
                  {input.file.name}
                </strong>
                <span className="text-[11.5px] text-[#8a99ad]">
                  {formatSize(input.file.size)} · click to choose another file
                </span>
              </span>
            ) : (
              <span>
                <strong className="block text-[13px] font-medium text-[#617895]">
                  Choose a file or drop it here
                </strong>
                <span className="text-[11.5px] text-[#8a99ad]">.pdf or .txt · up to 10 MB</span>
              </span>
            )}
          </label>
          <FieldError id={`${id}-file-error`} message={errors.file} />
        </div>

        <div className="mt-4">
          <label htmlFor={`${id}-title-input`} className="mb-1.5 block text-[12px] font-medium text-[#5b6b80]">
            Title
          </label>
          <input
            id={`${id}-title-input`}
            value={input.title}
            onChange={(event) => update("title", event.target.value)}
            maxLength={MAX_TITLE_LENGTH}
            disabled={submitting}
            placeholder="e.g. River response — update"
            aria-invalid={!!errors.title}
            aria-describedby={errors.title ? `${id}-title-error` : undefined}
            className={fieldClass(!!errors.title)}
          />
          <FieldError id={`${id}-title-error`} message={errors.title} />
        </div>

        <div className="mt-4 grid gap-4 sm:grid-cols-[minmax(0,180px)_minmax(0,1fr)]">
          <div>
            <label htmlFor={`${id}-date`} className="mb-1.5 block text-[12px] font-medium text-[#5b6b80]">
              Report date
            </label>
            <input
              id={`${id}-date`}
              type="date"
              value={input.report_date}
              onChange={(event) => update("report_date", event.target.value)}
              disabled={submitting}
              aria-invalid={!!errors.report_date}
              aria-describedby={errors.report_date ? `${id}-date-error` : undefined}
              className={fieldClass(!!errors.report_date)}
            />
            <FieldError id={`${id}-date-error`} message={errors.report_date} />
          </div>
          <div>
            <label htmlFor={`${id}-url`} className="mb-1.5 block text-[12px] font-medium text-[#5b6b80]">
              Source link <span className="font-normal text-[#9aa4b1]">(optional)</span>
            </label>
            <input
              id={`${id}-url`}
              type="url"
              inputMode="url"
              value={input.source_url}
              onChange={(event) => update("source_url", event.target.value)}
              disabled={submitting}
              placeholder="https://"
              aria-invalid={!!errors.source_url}
              aria-describedby={errors.source_url ? `${id}-url-error` : undefined}
              className={fieldClass(!!errors.source_url)}
            />
            <FieldError id={`${id}-url-error`} message={errors.source_url} />
          </div>
        </div>

        {submitError && (
          <p
            role="alert"
            className="mt-4 flex gap-2 rounded-lg border border-[#efd3cd] bg-[#fdf4f2] p-3 text-[12.5px] leading-relaxed text-[#8a4234]"
          >
            <TriangleAlert size={15} className="mt-0.5 shrink-0" />
            {submitError}
          </p>
        )}

        <div className="mt-6 flex items-center justify-end gap-2">
          <button
            type="button"
            onClick={() => dialogRef.current?.close()}
            disabled={submitting}
            className="rounded-lg px-3.5 py-2.5 text-[12.5px] font-medium text-[#6b7888] hover:enabled:bg-[#eef1f4]"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={submitting}
            className="inline-flex items-center gap-2 rounded-lg bg-[#2b405b] px-4 py-2.5 text-[12.5px] font-medium text-white hover:enabled:bg-[#345778] disabled:opacity-80"
          >
            {submitting ? (
              <>
                <LoaderCircle size={15} className="animate-spin" /> Adding report…
              </>
            ) : (
              <>
                <Upload size={15} /> Add report
              </>
            )}
          </button>
        </div>
      </form>
    </dialog>
  );
}

function FieldError({ id, message }: { id: string; message?: string }) {
  if (!message) return null;
  return (
    <p id={id} className="mt-1.5 text-[11.5px] text-[#b4593f]">
      {message}
    </p>
  );
}
