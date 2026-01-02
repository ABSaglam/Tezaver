"""
Mark Crash Rallies - Batch Archetype Assignment
================================================

diamond_crash_classification.csv'den okunan CRASH rally'leri
RallyStore'da archetype='CRASH' olarak işaretler.
"""

import pandas as pd
from pathlib import Path
from tezaver.core.rally_store import RallyStore
from tezaver.core.logging_utils import get_logger

logger = get_logger(__name__)

def main():
    logger.info("=" * 70)
    logger.info("CRASH RALLY BATCH MARKING")
    logger.info("=" * 70)
    
    # Load crash classification
    crash_file = Path(".tezaver_matrix/harmony_mining/diamond_crash_classification.csv")
    
    if not crash_file.exists():
        logger.error(f"Crash classification file not found: {crash_file}")
        return
    
    df = pd.read_csv(crash_file)
    
    # Filter crash rallies
    crash_rallies = df[df['is_crash'] == True]
    
    logger.info(f"\n📊 Total rallies: {len(df)}")
    logger.info(f"🔴 Crash rallies: {len(crash_rallies)}")
    
    if len(crash_rallies) == 0:
        logger.warning("No crash rallies found!")
        return
    
    # Batch update
    store = RallyStore()
    updated_count = 0
    failed_count = 0
    
    logger.info(f"\n⏳ Updating {len(crash_rallies)} rallies...")
    
    for idx, row in crash_rallies.iterrows():
        rally_id = row['rally_id']
        
        try:
            # Get rally
            doc = store.get_rally(rally_id)
            
            if not doc:
                logger.warning(f"Rally not found: {rally_id}")
                failed_count += 1
                continue
            
            # Update molder_data
            molder = doc.get('molder_data', {}) or {}
            molder['archetype'] = 'CRASH'
            molder['crash_detected'] = True
            molder['crash_severity'] = row.get('crash_severity', 0)
            molder['updated_at'] = pd.Timestamp.now()
            
            # Also update rev_data for consistency
            rev = doc.get('rev_data', {}) or {}
            rev['archetype'] = 'CRASH'
            rev['updated_at'] = pd.Timestamp.now()
            
            # Save
            store.upsert_rally(rally_id, molder, layer='molder')
            store.upsert_rally(rally_id, rev, layer='rev')
            
            updated_count += 1
            
            if updated_count % 10 == 0:
                logger.info(f"   Progress: {updated_count}/{len(crash_rallies)}")
        
        except Exception as e:
            logger.error(f"Failed to update {rally_id}: {e}")
            failed_count += 1
    
    logger.info("\n" + "=" * 70)
    logger.info("RESULTS")
    logger.info("=" * 70)
    logger.info(f"✅ Updated: {updated_count}")
    logger.info(f"❌ Failed: {failed_count}")
    logger.info("=" * 70)
    
    logger.info("\n📂 Next step: Check Kalıpçı → Katalog tab")
    logger.info("   Filter: TF=15m, Kalıp=CRASH")
    logger.info(f"   Expected: {updated_count} rallies")


if __name__ == "__main__":
    main()
