import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const root = path.resolve(".");
const dataDir = path.join(root, "data");
const outputXlsx = path.join(dataDir, "autodata_demo_business_dataset.xlsx");
const outputCsv = path.join(dataDir, "autodata_demo_orders.csv");
const outputJson = path.join(dataDir, "autodata_demo_orders.json");
const previewPath = path.join(root, "outputs", "autodata_demo_dashboard.png");

await fs.mkdir(dataDir, { recursive: true });
await fs.mkdir(path.join(root, "outputs"), { recursive: true });

const regions = ["North", "South", "East", "West"];
const categories = ["Electronics", "Furniture", "Office Supplies", "Home", "Grocery"];
const segments = ["Consumer", "Corporate", "Small Business"];
const channels = ["Online", "Retail", "Partner"];
const baseDate = new Date("2025-01-01T00:00:00Z");

function round(value, digits = 2) {
  const factor = 10 ** digits;
  return Math.round(value * factor) / factor;
}

function isoDate(date) {
  return date.toISOString().slice(0, 10);
}

const rows = [];
for (let i = 0; i < 240; i += 1) {
  const date = new Date(baseDate);
  date.setUTCDate(baseDate.getUTCDate() + i * 3);
  const region = regions[i % regions.length];
  const category = categories[(i * 2 + Math.floor(i / 13)) % categories.length];
  const segment = segments[(i + Math.floor(i / 17)) % segments.length];
  const channel = channels[(i + Math.floor(i / 11)) % channels.length];
  const quantity = 1 + ((i * 7) % 9);
  const unitPrice =
    {
      Electronics: 420,
      Furniture: 310,
      "Office Supplies": 85,
      Home: 140,
      Grocery: 35,
    }[category] + (i % 8) * 6;
  const discount = round(((i * 3) % 28) / 100, 2);
  const revenue = round(quantity * unitPrice * (1 - discount), 2);
  const costRate =
    {
      Electronics: 0.68,
      Furniture: 0.73,
      "Office Supplies": 0.58,
      Home: 0.61,
      Grocery: 0.76,
    }[category] + (discount > 0.18 ? 0.09 : 0);
  let profit = round(revenue * (1 - costRate) - (channel === "Partner" ? 18 : 7), 2);
  if (i % 53 === 0) {
    profit = round(profit - revenue * 0.42, 2);
  }
  rows.push({
    order_id: `ORD-${String(i + 1).padStart(4, "0")}`,
    order_date: isoDate(date),
    region,
    product_category: category,
    customer_segment: segment,
    sales_channel: channel,
    quantity,
    unit_price: unitPrice,
    discount,
    sales: revenue,
    profit,
    customer_id: `CUST-${String(1000 + ((i * 19) % 85)).padStart(4, "0")}`,
  });
}

const headers = Object.keys(rows[0]);
const csvEscape = (value) => {
  const text = String(value ?? "");
  return /[",\n]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
};
await fs.writeFile(
  outputCsv,
  [headers.join(","), ...rows.map((row) => headers.map((header) => csvEscape(row[header])).join(","))].join("\n"),
  "utf8",
);
await fs.writeFile(outputJson, JSON.stringify(rows, null, 2), "utf8");

const byCategory = new Map();
const byMonth = new Map();
const bySegment = new Map();
const discountBins = new Map([
  ["0-5%", { discount_band: "0-5%", orders: 0, avg_profit: 0, total_profit: 0 }],
  ["6-15%", { discount_band: "6-15%", orders: 0, avg_profit: 0, total_profit: 0 }],
  ["16%+", { discount_band: "16%+", orders: 0, avg_profit: 0, total_profit: 0 }],
]);

for (const row of rows) {
  const month = row.order_date.slice(0, 7);
  const category = byCategory.get(row.product_category) ?? {
    product_category: row.product_category,
    sales: 0,
    profit: 0,
    orders: 0,
  };
  category.sales += row.sales;
  category.profit += row.profit;
  category.orders += 1;
  byCategory.set(row.product_category, category);

  const monthRow = byMonth.get(month) ?? { month, sales: 0, profit: 0, orders: 0 };
  monthRow.sales += row.sales;
  monthRow.profit += row.profit;
  monthRow.orders += 1;
  byMonth.set(month, monthRow);

  const segment = bySegment.get(row.customer_segment) ?? {
    customer_segment: row.customer_segment,
    sales: 0,
    profit: 0,
    orders: 0,
  };
  segment.sales += row.sales;
  segment.profit += row.profit;
  segment.orders += 1;
  bySegment.set(row.customer_segment, segment);

  const band = row.discount <= 0.05 ? "0-5%" : row.discount <= 0.15 ? "6-15%" : "16%+";
  const bin = discountBins.get(band);
  bin.orders += 1;
  bin.total_profit += row.profit;
}

for (const bin of discountBins.values()) {
  bin.avg_profit = round(bin.total_profit / bin.orders, 2);
}

const categoryRows = [...byCategory.values()]
  .map((row) => ({
    ...row,
    sales: round(row.sales),
    profit: round(row.profit),
    margin: round(row.profit / row.sales, 4),
  }))
  .sort((a, b) => b.sales - a.sales);
const monthRows = [...byMonth.values()].map((row) => ({
  ...row,
  sales: round(row.sales),
  profit: round(row.profit),
}));
const segmentRows = [...bySegment.values()]
  .map((row) => ({
    ...row,
    sales: round(row.sales),
    profit: round(row.profit),
    margin: round(row.profit / row.sales, 4),
  }))
  .sort((a, b) => b.margin - a.margin);
const discountRows = [...discountBins.values()];

const workbook = Workbook.create();
const dashboard = workbook.worksheets.add("Dashboard");
const orders = workbook.worksheets.add("Orders");
const summary = workbook.worksheets.add("Summary Tables");
const dictionary = workbook.worksheets.add("Data Dictionary");
const questions = workbook.worksheets.add("Demo Questions");
const checks = workbook.worksheets.add("QA Checks");

for (const sheet of [dashboard, orders, summary, dictionary, questions, checks]) {
  sheet.showGridLines = false;
}

orders.getRangeByIndexes(0, 0, rows.length + 1, headers.length).values = [
  headers,
  ...rows.map((row) => headers.map((header) => row[header])),
];
orders.getRange("A1:L1").format = {
  fill: "#155E75",
  font: { bold: true, color: "#FFFFFF" },
  borders: { preset: "all", style: "thin", color: "#CFE8F3" },
};
orders.getRange("A:L").format.columnWidthPx = 118;
orders.getRange("B:B").setNumberFormat("yyyy-mm-dd");
orders.getRange("I:I").setNumberFormat("0.0%");
orders.getRange("H:H").setNumberFormat("$#,##0.00");
orders.getRange("J:K").setNumberFormat("$#,##0.00");
orders.freezePanes.freezeRows(1);
orders.tables.add(`A1:L${rows.length + 1}`, true, "OrdersTable");

dashboard.getRange("A1:H2").merge();
dashboard.getRange("A1").values = [["Autonomous Data Analysis Agent - Demo Dataset"]];
dashboard.getRange("A1:H2").format = {
  fill: "#0F172A",
  font: { bold: true, color: "#FFFFFF", size: 16 },
  horizontalAlignment: "center",
  verticalAlignment: "center",
};
dashboard.getRange("A4:A8").values = [
  ["Total Sales"],
  ["Total Profit"],
  ["Profit Margin"],
  ["Orders"],
  ["Negative Profit Orders"],
];
dashboard.getRange("B4:B8").formulas = [
  [`=SUM(Orders!J2:J${rows.length + 1})`],
  [`=SUM(Orders!K2:K${rows.length + 1})`],
  ["=B5/B4"],
  [`=COUNTA(Orders!A2:A${rows.length + 1})`],
  [`=COUNTIF(Orders!K2:K${rows.length + 1},"<0")`],
];
dashboard.getRange("A4:B8").format = {
  fill: "#ECFEFF",
  borders: { preset: "all", style: "thin", color: "#A5F3FC" },
};
dashboard.getRange("A:A").format.columnWidthPx = 155;
dashboard.getRange("B:B").format.columnWidthPx = 105;
dashboard.getRange("D:H").format.columnWidthPx = 118;
dashboard.getRange("J:M").format.columnWidthPx = 118;
dashboard.getRange("A4:A8").format = { font: { bold: true, color: "#164E63" } };
dashboard.getRange("B4:B5").setNumberFormat("$#,##0");
dashboard.getRange("B6").setNumberFormat("0.0%");
dashboard.getRange("B7:B8").setNumberFormat("0");

summary.getRangeByIndexes(0, 0, categoryRows.length + 1, 5).values = [
  ["product_category", "sales", "profit", "margin", "orders"],
  ...categoryRows.map((row) => [row.product_category, row.sales, row.profit, row.margin, row.orders]),
];
summary.getRangeByIndexes(0, 7, monthRows.length + 1, 4).values = [
  ["month", "sales", "profit", "orders"],
  ...monthRows.map((row) => [row.month, row.sales, row.profit, row.orders]),
];
summary.getRangeByIndexes(0, 13, segmentRows.length + 1, 5).values = [
  ["customer_segment", "sales", "profit", "margin", "orders"],
  ...segmentRows.map((row) => [row.customer_segment, row.sales, row.profit, row.margin, row.orders]),
];
summary.getRangeByIndexes(0, 20, discountRows.length + 1, 4).values = [
  ["discount_band", "orders", "avg_profit", "total_profit"],
  ...discountRows.map((row) => [row.discount_band, row.orders, row.avg_profit, round(row.total_profit)]),
];
summary.getRange("A1:E1").format = { fill: "#155E75", font: { bold: true, color: "#FFFFFF" } };
summary.getRange("H1:K1").format = { fill: "#155E75", font: { bold: true, color: "#FFFFFF" } };
summary.getRange("N1:R1").format = { fill: "#155E75", font: { bold: true, color: "#FFFFFF" } };
summary.getRange("U1:X1").format = { fill: "#155E75", font: { bold: true, color: "#FFFFFF" } };
summary.getRange("B:C").setNumberFormat("$#,##0");
summary.getRange("D:D").setNumberFormat("0.0%");
summary.getRange("I:J").setNumberFormat("$#,##0");
summary.getRange("O:P").setNumberFormat("$#,##0");
summary.getRange("Q:Q").setNumberFormat("0.0%");
summary.getRange("W:X").setNumberFormat("$#,##0");
summary.freezePanes.freezeRows(1);

dashboard.getRange("D4:H4").values = [["Category", "Sales", "Profit", "Margin", "Orders"]];
dashboard.getRange("D5:H9").formulas = [
  ["='Summary Tables'!A2", "='Summary Tables'!B2", "='Summary Tables'!C2", "='Summary Tables'!D2", "='Summary Tables'!E2"],
  ["='Summary Tables'!A3", "='Summary Tables'!B3", "='Summary Tables'!C3", "='Summary Tables'!D3", "='Summary Tables'!E3"],
  ["='Summary Tables'!A4", "='Summary Tables'!B4", "='Summary Tables'!C4", "='Summary Tables'!D4", "='Summary Tables'!E4"],
  ["='Summary Tables'!A5", "='Summary Tables'!B5", "='Summary Tables'!C5", "='Summary Tables'!D5", "='Summary Tables'!E5"],
  ["='Summary Tables'!A6", "='Summary Tables'!B6", "='Summary Tables'!C6", "='Summary Tables'!D6", "='Summary Tables'!E6"],
];
dashboard.getRange("D4:H4").format = { fill: "#155E75", font: { bold: true, color: "#FFFFFF" } };
dashboard.getRange("E5:F9").setNumberFormat("$#,##0");
dashboard.getRange("G5:G9").setNumberFormat("0.0%");

const categoryChart = dashboard.charts.add("bar", dashboard.getRange("D4:F9"));
categoryChart.title = "Sales and Profit by Category";
categoryChart.hasLegend = true;
categoryChart.yAxis = { numberFormatCode: "$#,##0" };
categoryChart.setPosition("A11", "H28");

dashboard.getRange("J4:M4").values = [["Month", "Sales", "Profit", "Orders"]];
dashboard.getRange("J5:M16").formulas = monthRows.slice(0, 12).map((_, index) => [
  `='Summary Tables'!H${index + 2}`,
  `='Summary Tables'!I${index + 2}`,
  `='Summary Tables'!J${index + 2}`,
  `='Summary Tables'!K${index + 2}`,
]);
dashboard.getRange("J4:M4").format = { fill: "#155E75", font: { bold: true, color: "#FFFFFF" } };
dashboard.getRange("K5:L16").setNumberFormat("$#,##0");
const trendChart = dashboard.charts.add("line", dashboard.getRange("J4:L16"));
trendChart.title = "Monthly Sales and Profit Trend";
trendChart.hasLegend = true;
trendChart.yAxis = { numberFormatCode: "$#,##0" };
trendChart.setPosition("J18", "S35");

dictionary.getRange("A1:D1").values = [["Column", "Type", "Meaning", "Example Analysis Use"]];
dictionary.getRange("A2:D13").values = [
  ["order_id", "Text", "Unique order identifier", "Trace anomalies"],
  ["order_date", "Date", "Order date", "Trend analysis"],
  ["region", "Text", "Sales region", "Segmentation"],
  ["product_category", "Text", "Category sold", "Aggregation/ranking"],
  ["customer_segment", "Text", "Customer segment", "Margin segmentation"],
  ["sales_channel", "Text", "Channel used", "Channel comparison"],
  ["quantity", "Number", "Units sold", "Volume analysis"],
  ["unit_price", "Currency", "Price before discount", "Pricing analysis"],
  ["discount", "Percent", "Discount rate", "Profit relationship"],
  ["sales", "Currency", "Final order revenue", "Revenue questions"],
  ["profit", "Currency", "Order profit", "Profitability questions"],
  ["customer_id", "Text", "Customer identifier", "Customer-level follow-up"],
];
dictionary.getRange("A1:D1").format = { fill: "#155E75", font: { bold: true, color: "#FFFFFF" } };
dictionary.getRange("A:D").format.columnWidthPx = 180;

questions.getRange("A1:D1").values = [["Question", "Operation", "Expected Chart", "Success Metric"]];
questions.getRange("A2:D7").values = [
  ["Which product categories generated the highest total revenue?", "Aggregation/ranking", "Bar", "Correct answer from dataset"],
  ["How have monthly sales and profit changed over time?", "Trend analysis", "Line", "Appropriate visualization"],
  ["Which customer segment is most profitable, and where are margins weakest?", "Segmentation", "Bar/table", "Narrative with limitations"],
  ["Is discount level related to profit?", "Correlation/relationship", "Scatter or banded bar", "Insight plus uncertainty"],
  ["Are there unusual orders with very high sales, high discounts, or negative profit?", "Anomaly detection", "Distribution/table", "Business follow-up"],
  ["For that weakest-margin segment, which categories are causing the problem?", "Contextual follow-up", "Bar/table", "Session history"],
];
questions.getRange("A1:D1").format = { fill: "#155E75", font: { bold: true, color: "#FFFFFF" } };
questions.getRange("A:D").format.columnWidthPx = 230;
questions.getRange("A2:A7").format.wrapText = true;

checks.getRange("A1:B1").values = [["Check", "Formula / Result"]];
checks.getRange("A2:A6").values = [
  ["Order count matches source"],
  ["Total sales"],
  ["Total profit"],
  ["Negative profit orders"],
  ["Blank critical fields"],
];
checks.getRange("B2:B6").formulas = [
  [`=COUNTA(Orders!A2:A${rows.length + 1})`],
  [`=SUM(Orders!J2:J${rows.length + 1})`],
  [`=SUM(Orders!K2:K${rows.length + 1})`],
  [`=COUNTIF(Orders!K2:K${rows.length + 1},"<0")`],
  [`=COUNTBLANK(Orders!A2:E${rows.length + 1})`],
];
checks.getRange("A1:B1").format = { fill: "#155E75", font: { bold: true, color: "#FFFFFF" } };
checks.getRange("A:B").format.columnWidthPx = 210;
checks.getRange("B3:B4").setNumberFormat("$#,##0");

const inspect = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 50 },
  summary: "formula error scan",
});
console.log(inspect.ndjson);

const preview = await workbook.render({
  sheetName: "Dashboard",
  autoCrop: "all",
  scale: 1,
  format: "png",
});
await fs.writeFile(previewPath, new Uint8Array(await preview.arrayBuffer()));

const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputXlsx);
console.log(JSON.stringify({ outputXlsx, outputCsv, outputJson, previewPath }, null, 2));
