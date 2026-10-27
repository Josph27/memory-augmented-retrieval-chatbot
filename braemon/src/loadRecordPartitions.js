// Keep the two requests independent: a failure must not discard the other list.
export async function loadRecordPartitions(activeRequest, inactiveRequest, kind) {
	const results = await Promise.allSettled([activeRequest, inactiveRequest]);
	const records = [];
	const failed = [];
	for (const [index, name] of ["active", "inactive"].entries()) {
		const result = results[index];
		if (result.status === "fulfilled") {
			records.push(...result.value);
		} else {
			console.error(`${name === "active" ? "Active" : "Inactive"} ${kind} fetch failed:`, result.reason);
			failed.push(name);
		}
	}
	return { records, failed };
}
