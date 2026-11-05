import fs from "fs";
import path from "path";

function walk(dir, out = []) {
  for (const name of fs.readdirSync(dir)) {
    const p = path.join(dir, name);
    if (fs.statSync(p).isDirectory()) walk(p, out);
    else if (name.endsWith(".vue")) out.push(p);
  }
  return out;
}

const root = path.resolve("src");
for (const file of walk(root)) {
  let s = fs.readFileSync(file, "utf8");
  const before = s;
  // 修复批量重排时 join('\\n') 写成字面量 \n 的问题（仅块边界）
  s = s.split("</template>\\n\\n<script").join("</template>\n\n<script");
  s = s.split("</script>\\n\\n<style").join("</script>\n\n<style");
  s = s.split("</style>\\n").join("</style>\n");
  if (s !== before) {
    fs.writeFileSync(file, s, "utf8");
    console.log("fixed", path.relative(process.cwd(), file));
  } else {
    console.log("ok   ", path.relative(process.cwd(), file));
  }
}
