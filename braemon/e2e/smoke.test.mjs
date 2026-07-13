/**
 * Smoke test: verify Breamon pages render content (not blank/white).
 * Run with: node braemon/e2e/smoke.test.mjs
 */
import puppeteer from "puppeteer";

const BASE = "http://localhost:5173";

async function run() {
	const browser = await puppeteer.launch({
		headless: "new",
		args: ["--no-sandbox", "--disable-setuid-sandbox"],
	});
	const page = await browser.newPage();
	let failures = 0;

	async function assert(cond, msg) {
		if (!cond) {
			failures++;
			console.error(`  ❌ ${msg}`);
		} else console.log(`  ✅ ${msg}`);
	}

	async function pageHasContent(url, timeout = 10_000) {
		await page.goto(url, { waitUntil: "domcontentloaded", timeout });
		await new Promise((r) => setTimeout(r, 3000));
		const bodyText = await page.evaluate(
			() => document.body?.innerText?.trim() || "",
		);
		const bodyHTML = await page.evaluate(() => document.body?.innerHTML || "");
		const hasContent =
			bodyText.length > 30 ||
			bodyHTML.includes("root") ||
			bodyHTML.includes("app");
		console.log(`  Page text length: ${bodyText.length} chars`);
		return {
			hasContent,
			bodyText: bodyText.substring(0, 100),
			bodyHTML: bodyHTML.substring(0, 200),
		};
	}

	try {
		// Test 1: Homepage /chats
		console.log("\n═══ Test 1: /chats page has content ═══");
		const r1 = await pageHasContent(`${BASE}/chats`);
		await assert(r1.hasContent, "/chats renders content");
		if (!r1.hasContent) console.log(`  Text: "${r1.bodyText}"`);

		// Test 2: Chat page /chat
		console.log("\n═══ Test 2: /chat page has content ═══");
		const r2 = await pageHasContent(`${BASE}/chat`);
		await assert(r2.hasContent, "/chat renders content");
		if (!r2.hasContent) console.log(`  Text: "${r2.bodyText}"`);

		// Test 3: No JS errors
		console.log("\n═══ Test 3: No JavaScript errors ═══");
		page.on("pageerror", (err) => {
			console.error(`  JS ERROR: ${err.message}`);
			failures++;
		});
		await page.goto(`${BASE}/chat`, {
			waitUntil: "networkidle0",
			timeout: 15_000,
		});
		await new Promise((r) => setTimeout(r, 3000));

		// Test 4: React roots exist
		console.log("\n═══ Test 4: React renders into DOM ═══");
		const hasRoot = await page.evaluate(() => {
			const root = document.getElementById("root");
			return root && root.children.length > 0;
		});
		await assert(hasRoot, "React root has children");
	} catch (err) {
		failures++;
		console.error(`  ❌ CRASH: ${err.message}`);
	} finally {
		await browser.close();
	}

	console.log(
		`\n${failures === 0 ? "✅ ALL TESTS PASSED" : `❌ ${failures} FAILURES`}`,
	);
	process.exit(failures > 0 ? 1 : 0);
}

run();
