// src/lib/utils.ts

/**
 * Formats the constitution adherence levels into a string for the API.
 * @param levels - The adherence levels object (Record<string, number>).
 * @param constitutions - The list of available constitutions (ConstitutionItem[]).
 * @returns A formatted string or an empty string if no levels are set.
 */
export function formatAdherenceLevelsForApi(
    levels: Record<string, number>,
    constitutions: ConstitutionItem[]
): string {
    const activeIds = Object.keys(levels);
    if (activeIds.length === 0) {
        return "";
    }

    // Create a quick lookup map for constitution titles
    const constitutionsMap = constitutions.reduce((acc, c) => {
        acc[c.id] = c.title;
        return acc;
    }, {} as Record<string, string>);

    const levelLines = activeIds
        .map(id => {
            const title = constitutionsMap[id] || id; // Fallback to ID if title not found
            const level = levels[id];
            // Ensure level is within expected range, though validation might be better upstream
            const clampedLevel = Math.max(1, Math.min(5, level || 1));
            return `${title}: Level ${clampedLevel}/5`;
        })
        .sort(); // Sort alphabetically for consistent output

    return "# User-Specified Adherence Levels\n" + levelLines.join('\n');
}

/**
 * Wraps a synchronous operation function, executes it, and logs success based on its boolean return value.
 * Assumes the operation function handles its own specific logging/warnings for non-success cases.
 * @param description A description of the operation for logging.
 * @param operationFn A function that performs the operation and returns true on success, false otherwise.
 */
export function logOperationStatus(description: string, operationFn: () => boolean): void {
    const success = operationFn();
    if (success) {
        console.log(`[OK] ${description}`);
    }
    // Failures or non-applicable cases (e.g., session not found) are expected
    // to be logged within the operationFn or its helpers.
}


/**
 * Wraps an async function execution with standardized logging for success or failure.
 * Logs [OK] on success, [FAIL] on error, and re-throws the error.
 * @param description - A description of the action being performed (for logging).
 * @param fn - The async function to execute.
 * @returns The result of the executed function if successful, otherwise re-throws the error.
 */
export async function logExecution<T>(description: string, fn: () => Promise<T>): Promise<T> {
    try {
        const result = await fn();
        console.log(`[OK] ${description}`);
        return result;
    } catch (error: unknown) {
        console.error(`[FAIL] ${description}. Error:`, error instanceof Error ? error.message : error);
        throw error; // Re-throw the error so the caller can handle it if needed
    }
}
