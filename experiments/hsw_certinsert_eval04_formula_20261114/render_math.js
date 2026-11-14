const readline = require("node:readline");
const katex = require(process.argv[2]);

const input = readline.createInterface({ input: process.stdin });
input.on("line", (line) => {
  const expression = JSON.parse(line);
  try {
    katex.renderToString(expression, { throwOnError: true, strict: "error" });
    console.log("1");
  } catch {
    console.log("0");
  }
});
