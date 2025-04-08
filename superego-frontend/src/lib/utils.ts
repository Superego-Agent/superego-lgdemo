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
