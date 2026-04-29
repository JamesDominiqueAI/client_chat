import { spawn } from "node:child_process";

const port = process.env.PORT || "3000";
const child = spawn("next", ["dev", "-p", port], {
  stdio: "inherit",
  shell: process.platform === "win32",
});

child.on("exit", (code) => {
  process.exit(code ?? 0);
});
