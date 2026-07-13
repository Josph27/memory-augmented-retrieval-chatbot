/**
 * Breamon chat message rendering tests.
 *
 * Run with: node braemon/e2e/chat-messages.test.mjs
 * Requires: Breamon dev server (localhost:5173) + Chainlit backend (localhost:8000)
 */
import puppeteer from "puppeteer";

const BREAMON_URL = process.env.BREAMON_URL || "http://localhost:5173";
const TIMEOUT = 15_000;

function sleep(ms) {
	return new Promise((r) => setTimeout(r, ms));
}

async function run() {
	const browser = await puppeteer.launch({
		headless: "new",
		args: ["--no-sandbox", "--disable-setuid-sandbox"],
	});
	const page = await browser.newPage();
	let failures = 0;

	async function assert(condition, msg) {
		if (!condition) {
			failures++;
			console.error(`  ❌ FAIL: ${msg}`);
		} else {
			console.log(`  ✅ ${msg}`);
		}
	}

	/** Collect all chat bubble texts from the DOM */
	async function getBubbles(userMessages) {
		return await page.$$eval(
			'p[class*="whitespace-pre-wrap"]',
			(els, msgs) =>
				els.map((el, i) => ({
					index: i,
					text: (el.textContent || "").trim(),
					isUser: msgs.some((m) => el.textContent.includes(m)),
				})),
			userMessages,
		);
	}

	/** Wait for N agent bubbles to appear (non-user, non-empty) */
	async function waitForAgentBubbles(userMessages, minCount, timeoutMs) {
		const deadline = Date.now() + timeoutMs;
		while (Date.now() < deadline) {
			const bubbles = await getBubbles(userMessages);
			const agentBubbles = bubbles.filter(
				(b) => !b.isUser && b.text.length > 0,
			);
			if (agentBubbles.length >= minCount) return bubbles;
			await sleep(500);
		}
		return getBubbles(userMessages);
	}

	try {
		// ═══ Navigate ═══
		console.log("═══ SETUP: Navigating to chat ═══");
		await page.goto(`${BREAMON_URL}/chat`, {
			waitUntil: "domcontentloaded",
			timeout: TIMEOUT,
		});
		await sleep(3000);

		const INPUT = 'input[placeholder*="command"]';
		await page.waitForSelector(INPUT, { timeout: TIMEOUT });

		// ═══ Test 1: User messages appear in chat ═══
		console.log("\n═══ Test 1: User messages appear in chat ═══");
		const msg1 = "hello test user message";
		await page.click(INPUT);
		await page.type(INPUT, msg1, { delay: 20 });
		await sleep(200);

		// Click send button with material icon
		await page.evaluate(() => {
			const btns = document.querySelectorAll("button");
			for (const btn of btns) {
				const icon = btn.querySelector(".material-symbols-outlined");
				if (icon && icon.textContent.includes("send")) {
					btn.click();
					return;
				}
			}
		});
		console.log(`  Sent: "${msg1}"`);

		// Wait for user message to appear
		await sleep(2000);
		const bubbles1 = await getBubbles([msg1]);
		const userBubbles1 = bubbles1.filter((b) => b.isUser);
		await assert(
			userBubbles1.length >= 1,
			`User message visible (found ${userBubbles1.length})`,
		);

		// ═══ Test 2: No double / empty agent bubbles ═══
		console.log("\n═══ Test 2: No double or empty agent bubbles ═══");
		console.log("  Waiting for agent response...");
		const bubbles2 = await waitForAgentBubbles([msg1], 1, 25_000);
		const agentBubbles = bubbles2.filter((b) => !b.isUser);

		await assert(agentBubbles.length > 0, "Agent response present");

		for (const b of agentBubbles) {
			console.log(`  Agent #${b.index}: "${b.text.slice(0, 80)}"`);
		}

		// Check: no empty agent bubbles
		const emptyAgents = agentBubbles.filter((b) => b.text.length === 0);
		await assert(
			emptyAgents.length === 0,
			`No empty agent bubbles (found ${emptyAgents.length})`,
		);

		// Check: no ghost bubbles before the first agent response
		const allNonUser = bubbles2.filter((b) => !b.isUser);
		if (allNonUser.length > 0 && allNonUser[0].text.length === 0) {
			await assert(
				false,
				"First non-user bubble is empty — ghost bubble detected",
			);
		}

		// ═══ Test 3: Consistent across multiple turns ═══
		console.log("\n═══ Test 3: Consistent behavior across turns ═══");
		const msg2 = "second test message";
		await page.click(INPUT);
		await page.type(INPUT, msg2, { delay: 20 });
		await sleep(200);
		await page.evaluate(() => {
			const btns = document.querySelectorAll("button");
			for (const btn of btns) {
				const icon = btn.querySelector(".material-symbols-outlined");
				if (icon && icon.textContent.includes("send")) {
					btn.click();
					return;
				}
			}
		});
		console.log(`  Sent: "${msg2}"`);
		await sleep(2000);

		// Wait for second agent response
		const bubbles3 = await waitForAgentBubbles([msg1, msg2], 2, 25_000);
		const agentAfter2 = bubbles3.filter((b) => !b.isUser);
		const emptyAfter2 = agentAfter2.filter((b) => b.text.length === 0);

		await assert(
			emptyAfter2.length === 0,
			`Turn 2: No empty agent bubbles (found ${emptyAfter2.length})`,
		);

		const userAfter2 = bubbles3.filter((b) => b.isUser);
		await assert(
			userAfter2.length >= 2,
			`Turn 2: Both user messages visible (found ${userAfter2.length})`,
		);
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
