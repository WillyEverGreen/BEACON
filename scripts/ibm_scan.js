const checker = require("accessibility-checker");

async function main() {
  const target = process.argv[2];
  if (!target) {
    process.stderr.write("Usage: node scripts/ibm_scan.js <url>\n");
    process.exit(1);
    return;
  }

  try {
    const result = await checker.getCompliance(target, "IBM_Accessibility");
    const report = result && result.report ? result.report : { results: [] };
    process.stdout.write(JSON.stringify(report));
  } catch (error) {
    const message = error && error.message ? error.message : String(error);
    process.stderr.write(message + "\n");
    process.exit(2);
  }
}

main();
