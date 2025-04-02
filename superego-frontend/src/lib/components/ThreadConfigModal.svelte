<script lang="ts">
	import { fade, slide } from 'svelte/transition';
	import ConstitutionSelector from './ConstitutionSelector.svelte';
	import { activeConstitutionIds, compareSets } from '../stores';
	
	// Props
	export let visible = false;
	export let onClose = () => {};
	export let onSave = () => {};
	
	// State
	let mode: 'single' | 'compare' = 'single';
	let selectedConstitutionIds = $activeConstitutionIds;
	
	// Set up initial state
	$: if (visible) {
		selectedConstitutionIds = $activeConstitutionIds;
	}
	
	// Handle constitution selection change
	function handleConstitutionChange(newIds: string[]) {
		selectedConstitutionIds = newIds;
	}
	
	// Save configuration
	function saveConfig() {
		if (mode === 'single') {
			activeConstitutionIds.set(selectedConstitutionIds);
		}
		// Note: Compare mode is disabled for now, so no need to update compareSets
		
		onSave();
		onClose();
	}
</script>

{#if visible}
<div class="modal-backdrop" on:click={onClose} transition:fade={{ duration: 150 }}>
	<div class="modal-content" on:click|stopPropagation transition:slide={{ duration: 200 }}>
		<div class="modal-header">
			<h2>Thread Configuration</h2>
			<button class="close-button" on:click={onClose}>×</button>
		</div>
		
		<div class="modal-body">
			<!-- Mode Toggle (disabled for now as requested) -->
			<div class="mode-toggle-container">
				<span class="mode-label">MODE:</span>
				<div class="toggle-buttons">
					<button 
						class="toggle-button" 
						class:active={mode === 'single'} 
						on:click={() => mode = 'single'}
					>
						Single-Run
					</button>
					<button 
						class="toggle-button disabled" 
						class:active={mode === 'compare'} 
						disabled={true}
						title="Compare mode is currently disabled"
					>
						Compare
					</button>
				</div>
			</div>
			
			<!-- Constitution Selector -->
			<div class="selector-container">
				<h3>Select Constitution(s)</h3>
				<ConstitutionSelector 
					selectedConstitutionIds={selectedConstitutionIds}
					onChange={handleConstitutionChange}
				/>
			</div>
		</div>
		
		<div class="modal-footer">
			<button class="secondary-button" on:click={onClose}>Cancel</button>
			<button class="primary-button" on:click={saveConfig}>Save</button>
		</div>
	</div>
</div>
{/if}

<style>
	.modal-backdrop {
		position: fixed;
		top: 0;
		left: 0;
		right: 0;
		bottom: 0;
		background-color: rgba(0, 0, 0, 0.5);
		display: flex;
		justify-content: center;
		align-items: center;
		z-index: 1000;
	}
	
	.modal-content {
		background-color: var(--bg-elevated);
		border-radius: var(--radius-lg);
		width: 90%;
		max-width: 600px;
		max-height: 90vh;
		overflow-y: auto;
		box-shadow: var(--shadow-lg);
		display: flex;
		flex-direction: column;
	}
	
	.modal-header {
		padding: var(--space-md) var(--space-lg);
		border-bottom: 1px solid var(--input-border);
		display: flex;
		justify-content: space-between;
		align-items: center;
	}
	
	.modal-header h2 {
		margin: 0;
		font-size: 1.2rem;
		color: var(--text-primary);
	}
	
	.close-button {
		background: none;
		border: none;
		font-size: 1.5rem;
		cursor: pointer;
		color: var(--text-secondary);
		padding: 0;
		display: flex;
		align-items: center;
		justify-content: center;
		width: 32px;
		height: 32px;
		border-radius: 50%;
		transition: background-color 0.2s ease;
	}
	
	.close-button:hover {
		background-color: var(--bg-hover);
		color: var(--text-primary);
	}
	
	.modal-body {
		padding: var(--space-lg);
		display: flex;
		flex-direction: column;
		gap: var(--space-lg);
	}
	
	.modal-footer {
		padding: var(--space-md) var(--space-lg);
		border-top: 1px solid var(--input-border);
		display: flex;
		justify-content: flex-end;
		gap: var(--space-md);
	}
	
	.primary-button, .secondary-button {
		padding: var(--space-sm) var(--space-lg);
		border-radius: var(--radius-md);
		font-weight: 500;
		cursor: pointer;
		transition: all 0.2s ease;
	}
	
	.primary-button {
		background-color: var(--primary);
		color: white;
		border: none;
	}
	
	.primary-button:hover {
		background-color: var(--primary-light);
		transform: translateY(-2px);
	}
	
	.secondary-button {
		background-color: transparent;
		color: var(--text-primary);
		border: 1px solid var(--input-border);
	}
	
	.secondary-button:hover {
		background-color: var(--bg-hover);
	}
	
	.mode-toggle-container {
		display: flex;
		align-items: center;
		gap: var(--space-md);
	}
	
	.mode-label {
		font-weight: 600;
		color: var(--text-secondary);
	}
	
	.toggle-buttons {
		display: flex;
		border: 1px solid var(--input-border);
		border-radius: var(--radius-md);
		overflow: hidden;
	}
	
	.toggle-button {
		padding: var(--space-sm) var(--space-lg);
		background-color: var(--bg-surface);
		border: none;
		cursor: pointer;
		transition: all 0.2s ease;
	}
	
	.toggle-button:first-child {
		border-right: 1px solid var(--input-border);
	}
	
	.toggle-button.active {
		background-color: var(--primary);
		color: white;
	}
	
	.toggle-button.disabled {
		opacity: 0.6;
		cursor: not-allowed;
		text-decoration: line-through;
	}
	
	.selector-container {
		display: flex;
		flex-direction: column;
		gap: var(--space-md);
	}
	
	.selector-container h3 {
		margin: 0;
		font-size: 1rem;
		color: var(--text-primary);
	}
</style>
