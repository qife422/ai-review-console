import { Checkbox, FileUploaderButton, FileUploaderItem, InlineNotification, Modal, Select, SelectItem, TextInput } from "@carbon/react";
import { useEffect, useRef, useState } from "react";
import { api, ApiError } from "../api";
import type { AcceptedTask } from "../types";
import { errorMessage } from "../workflow";
import { createDemoFile, DEMO_SAMPLES } from "../demo";
import { isPublicDemo } from "../demoMode";

interface UploadDialogProps {
  onClose: () => void;
  onAccepted: (task: AcceptedTask) => void;
}

const supportedExtensions = /\.(pdf|docx|txt|md)$/i;

export function UploadDialog({ onClose, onAccepted }: UploadDialogProps) {
  const [file, setFile] = useState<File | null>(null);
  const [sampleId, setSampleId] = useState("");
  const [title, setTitle] = useState("");
  const [confirmed, setConfirmed] = useState(false);
  const [fileError, setFileError] = useState<string | null>(null);
  const [requestError, setRequestError] = useState<string | null>(null);
  const [requestId, setRequestId] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [idempotencyKey, setIdempotencyKey] = useState(() => crypto.randomUUID());
  const controller = useRef<AbortController | null>(null);
  const launcher = useRef(document.activeElement instanceof HTMLElement ? document.activeElement : null);

  useEffect(() => () => { controller.current?.abort(); if (launcher.current?.isConnected) launcher.current.focus(); }, []);

  function selectFile(nextFile: File | null) {
    setFile(nextFile);
    setRequestError(null);
    setRequestId(null);
    setIdempotencyKey(crypto.randomUUID());
    if (!nextFile) { setFileError(null); return; }
    setTitle(nextFile.name.replace(/\.[^.]+$/, "").slice(0, 180));
    setFileError(!supportedExtensions.test(nextFile.name) ? "仅支持 PDF、DOCX、TXT 和 MD。" :
      nextFile.size === 0 ? "不能上传空文件。" : nextFile.size > 10 * 1024 * 1024 ? "文件大小不能超过 10 MiB。" : null);
  }

  async function submit() {
    if (!file || fileError || !confirmed || !title.trim() || saving) return;
    setSaving(true);
    setRequestError(null);
    setRequestId(null);
    controller.current = new AbortController();
    try {
      const accepted = await api.upload(file, title, idempotencyKey, controller.current.signal);
      onAccepted(accepted);
    } catch (error) {
      if (controller.current.signal.aborted) return;
      setRequestError(errorMessage(error, "上传失败，请重试。"));
      setRequestId(error instanceof ApiError ? error.requestId : null);
    } finally {
      if (!controller.current.signal.aborted) setSaving(false);
    }
  }

  return (
    <Modal open selectorPrimaryFocus={isPublicDemo ? "#upload-sample" : "#upload-title"} launcherButtonRef={launcher} modalHeading={isPublicDemo ? "载入虚构样本" : "上传虚构文档"} modalLabel={isPublicDemo ? "在线沙盒" : "本地演示"} primaryButtonText={saving ? "正在提交" : isPublicDemo ? "开始体验" : "提交审查"} secondaryButtonText="取消" closeButtonLabel="关闭上传窗口" primaryButtonDisabled={saving || !file || !!fileError || !confirmed || !title.trim()} onRequestClose={() => { if (!saving) onClose(); }} onRequestSubmit={submit} preventCloseOnClickOutside hasScrollingContent>
      <div className="upload-form">
        <p className="modal-copy">{isPublicDemo ? "在线体验只允许下列预置 TXT 虚构样本，不接收本机文件。解析、评分和任务进度均为浏览器内模拟，刷新后恢复初始状态。" : <>支持 PDF、DOCX、TXT 和 MD，单文件 10 MiB，PDF 最多 200 页。正文须包含 <code>SYNTHETIC DEMO DOCUMENT</code>。</>}</p>
        <div className="upload-file-field">
          <p className="field-label" id="upload-document-label">虚构文档</p>
          {isPublicDemo ? <Select id="upload-sample" labelText="选择虚构样本" value={sampleId} disabled={saving} onChange={(event) => { const id = event.target.value; setSampleId(id); selectFile(id ? createDemoFile(id) : null); setTitle(DEMO_SAMPLES.find((sample) => sample.id === id)?.title ?? ""); }}><SelectItem value="" text="请选择一个预置样本" />{DEMO_SAMPLES.map((sample) => <SelectItem key={sample.id} value={sample.id} text={sample.title} />)}</Select> : <FileUploaderButton id="upload-document" accept={[".pdf", ".docx", ".txt", ".md"]} buttonKind="tertiary" disabled={saving} multiple={false} labelText="选择文档" disableLabelChanges onChange={(event) => selectFile(event.target.files?.[0] ?? null)} aria-describedby="upload-document-label" />}
          {file && <FileUploaderItem name={file.name} status={saving ? "uploading" : "edit"} invalid={!!fileError} errorSubject="文件不符合要求" errorBody={fileError ?? undefined} iconDescription="移除文件" disabled={saving} onDelete={() => selectFile(null)} />}
          {file && !fileError && <p className="field-helper">{(file.size / 1024).toFixed(1)} KiB。{isPublicDemo ? DEMO_SAMPLES.find((sample) => sample.id === sampleId)?.description : "文件结构、虚构标识和正文将在后台校验。"}</p>}
        </div>
        <TextInput id="upload-title" labelText="案件标题" value={title} maxLength={180} disabled={saving} readOnly={isPublicDemo} helperText={isPublicDemo ? "使用所选虚构样本的固定标题，不输入真实业务资料。" : "使用便于识别的文档名称，最多 180 个字符。"} onChange={(event) => { setTitle(event.target.value); setIdempotencyKey(crypto.randomUUID()); setRequestError(null); }} />
        <Checkbox id="synthetic-confirmation" labelText="我确认该文档仅含虚构演示数据，不含公司机密或真实个人资料。" checked={confirmed} disabled={saving} onChange={(_, { checked }) => setConfirmed(checked)} />
        <p className="field-helper">{isPublicDemo ? "仅在本页内模拟操作，不会上传文档或决定内容。请勿在理由中填写真实姓名、客户资料或秘密；刷新即重置。" : "提交成功后由后台继续处理，关闭页面不会取消已接受的任务。所有案件均需人工决定。"}</p>
        {requestError && <InlineNotification kind="error" lowContrast hideCloseButton title="无法提交文档" subtitle={`${requestError}${requestId ? ` 请求编号：${requestId}` : ""}`} />}
      </div>
    </Modal>
  );
}
