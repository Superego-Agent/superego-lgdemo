<script lang="ts">
	import { availableConstitutions } from '../stores';
	import { fade } from 'svelte/transition';
	
	// Props
	export let selectedConstitutionIds: string[] = ['none'];
	export let onChange: (ids: string[]) => void = () => {};
	
	// Constants
	const SEPARATOR = '+'; // Same separator as in cli.py (CONSTITUTION_SEPARATOR)
	
	// State
	let searchTerm: string = '';
	
	// Derived state for filtering constitutions
	$: filteredConstitutions = $availableConstitutions.filter(constitution => {
		const searchLower = searchTerm.toLowerCase();
		return (
			constitution.id.toLowerCase().includes(searchLower) ||
			(constitution.description?.toLowerCase() || '').includes(searchLower)
		);
	});
	
	// Toggle a constitution selection
	function toggleConstitution(id: string) {
		let newSelection: string[];
		
		// Special handling for 'none' - it shouldn't be combined with others
		if (id === 'none') {
			newSelection = ['none'];
		} else {
			// If currently only 'none' is selected, replace it
			if (selectedConstitutionIds.length === 1 && selectedConstitutionIds[0] === 'none') {
				newSelection = [id];
			} else {
				// Toggle the selection
				if (selectedConstitutionIds.includes(id)) {
					newSelection = selectedConstitutionIds.filter(cid => cid !== id);
					// If nothing left, default to 'none'
					if (newSelection.length === 0) {
						newSelection = ['none'];
					}
				} else {
					// Add to selection, ensuring 'none' is removed if present
					newSelection = selectedConstitutionIds.filter(cid => cid !== 'none');
					newSelection.push(id);
				}
			}
		}
		
		// Notify parent component
		onChange(newSelection);
	}
</script>

<div class="constitution-selector">
	<div class="search-bar">
		<input
			type="text"
			placeholder="Search constitutions..."
			bind:value={searchTerm}
			class="search-input"
		/>
	</div>
	
	<div class="current-selection">
		<label>Selected:</label>
		<div class="chips-container">
			{#each selectedConstitutionIds as id (id)}
				<div class="chip" transition:fade|local={{ duration: 150 }}>
					<span class="chip-text">{id}</span>
					<button 
						class="chip-remove" 
						on:click|stopPropagation={() => toggleConstitution(id)}
						aria-label="Remove {id}"
					>×</button>
				</div>
			{:else}
				<div class="empty-selection">No constitutions selected</div>
			{/each}
		</div>
	</div>
	
	<div class="constitutions-table">
		<table>
			<thead>
				<tr>
					<th class="id-column">ID</th>
					<th>Description</th>
				</tr>
			</thead>
			<tbody>
				{#each filteredConstitutions as constitution (constitution.id)}
					<tr 
						class:selected={selectedConstitutionIds.includes(constitution.id)}
						on:click={() => toggleConstitution(constitution.id)}
						in:fade={{ duration: 150 }}
					>
						<td class="id-column">{constitution.id}</td>
						<td>{constitution.description}</td>
					</tr>
				{:else}
					<tr>
						<td colspan="2" class="empty-message">No constitutions found</td>
					</tr>
				{/each}
			</tbody>
		</table>
	</div>
</div>

<style>
	.constitution-selector {
		display: flex;
		flex-direction: column;
		gap: var(--space-md);
		max-height: 400px;
		width: 100%;
	}
	
	.search-bar {
		padding: 0;
	}
	
	.search-input {
		width: 100%;
		padding: var(--space-sm) var(--space-md);
		border: 1px solid var(--input-border);
		border-radius: var(--radius-md);
		color: var(--text-primary);
		background-color: var(--input-bg);
	}
	
	.current-selection {
		display: flex;
		gap: var(--space-md);
		align-items: flex-start;
		font-size: 0.9em;
	}
	
	.current-selection label {
		margin-top: var(--space-xs);
	}
	
	.chips-container {
		display: flex;
		flex-wrap: wrap;
		gap: var(--space-sm);
		flex-grow: 1;
	}
	
	.chip {
		display: flex;
		align-items: center;
		gap: 4px;
		padding: 2px 8px;
		background-color: var(--primary-transparent);
		border-radius: var(--radius-pill);
		border: 1px solid var(--primary-light);
		color: var(--primary);
		font-weight: 500;
		font-size: 0.9em;
		line-height: 1.5;
	}
	
	.chip-text {
		max-width: 120px;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	
	.chip-remove {
		background: none;
		border: none;
		color: var(--primary);
		font-size: 1.2em;
		cursor: pointer;
		padding: 0 2px;
		line-height: 1;
		border-radius: 50%;
		margin-left: 2px;
		display: flex;
		align-items: center;
		justify-content: center;
	}
	
	.chip-remove:hover {
		background-color: var(--primary-light);
		color: white;
	}
	
	.empty-selection {
		color: var(--text-secondary);
		font-style: italic;
		padding: var(--space-xs) 0;
	}
	
	.constitutions-table {
		overflow-y: auto;
		max-height: 250px;
		border: 1px solid var(--input-border);
		border-radius: var(--radius-md);
	}
	
	table {
		width: 100%;
		border-collapse: collapse;
	}
	
	thead {
		position: sticky;
		top: 0;
		background-color: var(--bg-elevated);
		z-index: 1;
	}
	
	th {
		text-align: left;
		padding: var(--space-sm) var(--space-md);
		border-bottom: 1px solid var(--input-border);
		font-weight: 600;
		color: var(--text-secondary);
	}
	
	td {
		padding: var(--space-sm) var(--space-md);
		border-bottom: 1px solid var(--input-border);
	}
	
	tr:last-child td {
		border-bottom: none;
	}
	
	.id-column {
		width: 120px;
		font-weight: 500;
	}
	
	tr {
		cursor: pointer;
		transition: background-color 0.2s ease;
	}
	
	tr:hover:not(.selected) {
		background-color: var(--bg-hover);
	}
	
	tr.selected {
		background-color: rgba(157, 70, 255, 0.15); /* More explicit purple with opacity */
		border-left: 3px solid var(--primary);
	}
	
	.empty-message {
		text-align: center;
		color: var(--text-secondary);
		font-style: italic;
		padding: var(--space-md);
	}
</style>
