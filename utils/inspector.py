from utils.cli_selector import InteractiveSelector

def inspect_items(items, display_func=None):
    if not items: return []
    
    display_items = [display_func(item) if display_func else str(item) for item in items]
    
    # Run the interactive selector
    selected_indices = InteractiveSelector(
        display_items, 
        title="Data Inspection (Select items to KEEP)",
        help_text="Space: Toggle | Enter: Toggle | C: Confirm | Q: Cancel"
    ).run_indices()
    
    if selected_indices is None: # User cancelled
        return items # Or maybe []? Usually cancel means keep everything or abort. Let's keep existing behavior of returning items.
        
    return [items[i] for i in selected_indices]

# Add run_indices to InteractiveSelector if it was removed or use run and map back
# Wait, I removed run_indices in the previous edit. I should add it back or change how I call it.
# Let me fix InteractiveSelector to include run_indices again.
