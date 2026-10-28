import { execFileSync } from "node:child_process";
import { cpSync, existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const frontend = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const destination = resolve(frontend, "../online-demo/out");
const staging = resolve(frontend, "../online-demo/.compile");
if (existsSync(staging) || existsSync(destination)) {
  throw new Error("Demo outputs already exist. Preserve them and select an explicitly reviewed rebuild path; never clean automatically.");
}
// Ignore all host .env files. Only the compiled, explicit demo flag is supplied.
execFileSync("npm", ["run", "build", "--", "--mode", "public-demo", "--outDir", staging], {
  cwd: frontend,
  env: { ...process.env, VITE_PUBLIC_DEMO: "true", VITE_API_BASE_URL: "" },
  stdio: "inherit",
});
mkdirSync(destination, { recursive: true });
cpSync(staging, destination, { recursive: true, errorOnExist: true, force: false });
const index = resolve(destination, "index.html");
let html = readFileSync(index, "utf8");
const policy = "default-src 'self'; connect-src 'none'; img-src 'self' data:; font-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'; object-src 'none'; base-uri 'none'; form-action 'none'; frame-src blob:; worker-src 'none'";
html = html.replace('<meta charset="UTF-8" />', `<meta charset="UTF-8" /><meta http-equiv="Content-Security-Policy" content="${policy}" />`)
  .replace("<title>AI Review Console</title>", "<title>AI Review Console | 仅虚构数据在线演示</title>")
  .replace("基于 Langflow 的虚构数据文档审查与决策演示", "仅预置虚构样本的浏览器交互沙盒，不连接真实 AI、Langflow 或数据库，不接收文件上传。");
writeFileSync(index, html);
const licenseDirectory = resolve(destination, "licenses");
mkdirSync(licenseDirectory, { recursive: true });
for (const [source, name] of [
  [resolve(frontend, "../LICENSE"), "PROJECT-APACHE-2.0.txt"],
  [resolve(frontend, "../THIRD_PARTY_NOTICES.md"), "THIRD_PARTY_NOTICES.md"],
  [resolve(frontend, "node_modules/@ibm/plex/LICENSE.txt"), "IBM-Plex-OFL-1.1.txt"],
  [resolve(frontend, "node_modules/react/LICENSE"), "React-MIT.txt"],
  [resolve(frontend, "node_modules/react-dom/LICENSE"), "React-DOM-MIT.txt"],
  [resolve(frontend, "node_modules/@carbon/react/LICENSE"), "Carbon-APACHE-2.0.txt"],
]) cpSync(source, resolve(licenseDirectory, name), { errorOnExist: true, force: false });
console.log(JSON.stringify({ directory: destination, mode: "public-demo", apiRequests: "blocked by CSP", userData: "memory only" }));
