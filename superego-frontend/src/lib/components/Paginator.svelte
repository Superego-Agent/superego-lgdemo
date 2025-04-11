<script lang="ts">
	import { onDestroy } from 'svelte';
	import ChevronLeftIcon from '~icons/fluent/chevron-left-24-regular';
	import ChevronRightIcon from '~icons/fluent/chevron-right-24-regular';

	// --- Props ---
	/** The full list of items to paginate */
	export let items: any[] = [];
	/** The width of the container where items are displayed */
	export let containerWidth: number = 0;
	/** The minimum desired width for each item */
	export let minItemWidth: number = 400;

	// --- Internal State ---
	let currentPage = 0;
	let itemsPerPage = 1;
	let totalPages = 1;
	let paginatedItems: any[] = [];

	// --- Reactive Calculations ---
	$: {
		itemsPerPage = Math.max(1, Math.floor(containerWidth / minItemWidth));
		totalPages = Math.ceil(items.length / itemsPerPage);
		// Clamp currentPage to valid range if totalPages or items change
		currentPage = Math.max(0, Math.min(currentPage, totalPages - 1));

		const startIndex = currentPage * itemsPerPage;
		const endIndex = startIndex + itemsPerPage;
		paginatedItems = items.slice(startIndex, endIndex);
		// console.log(`Paginator: w=${containerWidth}, minW=${minItemWidth}, ipp=${itemsPerPage}, totalP=${totalPages}, currentP=${currentPage}, items=${items.length}, paginated=${paginatedItems.length}`);
	}

	// --- Functions ---
	function goToPage(pageIndex: number) {
		currentPage = Math.max(0, Math.min(pageIndex, totalPages - 1));
	}
	function nextPage() {
		if (currentPage < totalPages - 1) {
			currentPage++;
		}
	}
	function prevPage() {
		if (currentPage > 0) {
			currentPage--;
		}
	}

	// Reset to page 0 if the underlying items array changes identity
	// This prevents staying on a potentially invalid page index
	let prevItems = items;
	$: {
		if (items !== prevItems) {
			// console.log("Paginator: Items array changed, resetting to page 0");
			currentPage = 0;
			prevItems = items;
		}
	}

</script>

{#if items.length > 0}
	<div class="paginator-wrapper">
		<!-- Default Slot: Exposes paginatedItems -->
		<slot {paginatedItems} />

		{#if totalPages > 1}
			<div class="pagination-controls">
				<button
					class="pagination-button"
					on:click={prevPage}
					disabled={currentPage === 0}
					aria-label="Previous Page"
				>
					<ChevronLeftIcon />
				</button>
				<div class="pagination-dots">
					{#each { length: totalPages } as _, i}
						<button
							class="dot"
							class:active={i === currentPage}
							on:click={() => goToPage(i)}
							aria-label="Go to page {i + 1}"
							aria-current={i === currentPage ? 'page' : undefined}
						></button>
					{/each}
				</div>
				<button
					class="pagination-button"
					on:click={nextPage}
					disabled={currentPage === totalPages - 1}
					aria-label="Next Page"
				>
					<ChevronRightIcon />
				</button>
			</div>
		{/if}
	</div>
{/if}

<style lang="scss">
	.paginator-wrapper {
		display: contents; // Allows slot content to flow naturally in parent flex/grid
	}

	.pagination-controls {
		display: flex;
		justify-content: center;
		align-items: center;
		padding: var(--space-xs) 0 var(--space-sm);
		flex-shrink: 0;
		gap: var(--space-md);
		margin-top: var(--space-sm); // Add some space above controls
	}

	.pagination-button {
		background: none;
		border: none;
		color: var(--text-secondary);
		cursor: pointer;
		padding: var(--space-xs);
		border-radius: var(--radius-sm);
		display: flex;
		align-items: center;
		justify-content: center;
		font-size: 1.2em;

		&:hover:not(:disabled) {
			background-color: var(--bg-hover);
			color: var(--text-primary);
		}

		&:disabled {
			color: var(--text-disabled);
			cursor: not-allowed;
		}
	}

	.pagination-dots {
		display: flex;
		gap: var(--space-xs);
	}

	.dot {
		width: 10px;
		height: 10px;
		border-radius: 50%;
		background-color: var(--secondary);
		border: none;
		padding: 0;
		cursor: pointer;
		transition: background-color 0.2s ease;

		&:hover {
			background-color: var(--text-secondary);
		}

		&.active {
			background-color: var(--primary);
		}
	}
</style>