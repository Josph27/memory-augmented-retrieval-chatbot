import assert from "node:assert/strict";
import test from "node:test";
import { loadRecordPartitions } from "../src/loadRecordPartitions.js";

for (const kind of ["documents", "memories"]) {
	test(`${kind}: retains successful partitions and reports failed ones`, async () => {
		const active = { id: "active" };
		const inactive = { id: "inactive" };
		const failure = new Error("synthetic failure");
		const originalError = console.error;
		const logs = [];
		console.error = (...args) => logs.push(args);
		try {
			for (const [activeFails, inactiveFails] of [[false, false], [true, false], [false, true], [true, true]]) {
				const result = await loadRecordPartitions(
					activeFails ? Promise.reject(failure) : Promise.resolve([active]),
					inactiveFails ? Promise.reject(failure) : Promise.resolve([inactive]),
					kind,
				);
				assert.deepEqual(result.records, [
					...(!activeFails ? [active] : []),
					...(!inactiveFails ? [inactive] : []),
				]);
				assert.deepEqual(result.failed, [
					...(activeFails ? ["active"] : []),
					...(inactiveFails ? ["inactive"] : []),
				]);
			}
			assert.equal(logs.length, 4);
			assert.ok(logs.every((entry) => entry[1] === failure));
		} finally {
			console.error = originalError;
		}
	});
}

test("malformed successful payload rejects instead of silently hiding data", async () => {
	await assert.rejects(loadRecordPartitions(Promise.resolve(null), Promise.resolve([]), "documents"), TypeError);
});
