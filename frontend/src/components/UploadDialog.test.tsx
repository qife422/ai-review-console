import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { jsonResponse } from "../test/fixtures";
import { UploadDialog } from "./UploadDialog";

afterEach(() => vi.unstubAllGlobals());

test("validates file size, format and the synthetic confirmation before submitting", () => {
  const { container } = render(<UploadDialog onClose={vi.fn()} onAccepted={vi.fn()} />);
  const input = container.querySelector('input[type="file"]')!;
  const submit = screen.getByRole("button", { name: "提交审查" });
  expect(submit).toBeDisabled();
  fireEvent.change(input, { target: { files: [new File(["invalid"], "document.exe")] } });
  expect(screen.getByText("仅支持 PDF、DOCX、TXT 和 MD。")).toBeInTheDocument();
  expect(submit).toBeDisabled();
  fireEvent.change(input, { target: { files: [new File(["SYNTHETIC DEMO DOCUMENT"], "synthetic.txt")] } });
  expect(screen.getByLabelText("案件标题")).toHaveValue("synthetic");
  expect(submit).toBeDisabled();
  fireEvent.click(screen.getByRole("checkbox"));
  expect(submit).toBeEnabled();
});

test("retries an unchanged upload with the same idempotency key and preserves multipart fields", async () => {
  const accepted = vi.fn();
  const requests: RequestInit[] = [];
  vi.stubGlobal("fetch", vi.fn((_: unknown, init: RequestInit) => {
    requests.push(init);
    return Promise.resolve(requests.length === 1 ? jsonResponse({ code: "queue_capacity_exceeded", detail: "Queue full", retryable: true }, 429) : jsonResponse({ case_id: "RC-NEW", document_version_id: "v1", job_id: "j1", status: "received" }, 202));
  }));
  const { container } = render(<UploadDialog onClose={vi.fn()} onAccepted={accepted} />);
  const file = new File(["SYNTHETIC DEMO DOCUMENT"], "synthetic.txt", { type: "text/plain" });
  fireEvent.change(container.querySelector('input[type="file"]')!, { target: { files: [file] } });
  fireEvent.click(screen.getByRole("checkbox"));
  fireEvent.click(screen.getByRole("button", { name: "提交审查" }));
  await screen.findByText("待处理任务已达到容量限制，请稍后提交。");
  fireEvent.click(screen.getByRole("button", { name: "提交审查" }));
  await waitFor(() => expect(accepted).toHaveBeenCalledWith(expect.objectContaining({ case_id: "RC-NEW" })));
  expect(new Headers(requests[0].headers).get("Idempotency-Key")).toBe(new Headers(requests[1].headers).get("Idempotency-Key"));
  const body = requests[0].body as FormData;
  expect(body.get("title")).toBe("synthetic");
  expect(body.get("synthetic_confirmed")).toBe("true");
  expect((body.get("file") as File).name).toBe(file.name);
  expect(new Headers(requests[0].headers).has("Content-Type")).toBe(false);
});
