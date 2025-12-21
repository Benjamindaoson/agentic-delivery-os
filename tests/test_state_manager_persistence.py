import asyncio
import os
import tempfile

from runtime.state.state_manager import StateManager, TaskState


def test_state_manager_persists_across_instances(tmp_path):
    async def _run():
        db_path = os.path.join(str(tmp_path), "tasks.db")
        # First instance: create and set state
        sm1 = StateManager(db_path=db_path)
        await sm1.initialize()
        task_id = "test-task-1"
        await sm1.create_task(task_id, {"name": "demo"})
        await sm1.update_task_state(task_id, TaskState.RUNNING.value, reason="started")

        # Second instance: new StateManager pointing to same sqlite file
        sm2 = StateManager(db_path=db_path)
        await sm2.initialize()
        state_record = await sm2.get_task_state(task_id)
        assert state_record is not None
        assert state_record.state == TaskState.RUNNING

    asyncio.run(_run())


