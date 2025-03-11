import asyncio
from azure.identity.aio import DefaultAzureCredential
from semantic_kernel.agents.azure_ai import AzureAIAgent


async def main() -> None:
    async with (
        DefaultAzureCredential() as creds,
        AzureAIAgent.create_client(credential=creds) as client,
    ):
        # Retrieve pre-created agent definitions for each role
        search_agent_def = await client.agents.get_agent(assistant_id="asst_y4afh4JDDXmCr97wEfvai2UD")
        # report_agent_def = await client.agents.get_agent(assistant_id="asst_PqBo7MNYVHlV0swYcmpcZeiB")
        # validation_agent_def = await client.agents.get_agent(assistant_id="asst_706GiYZuUksP5yeJpejpCHs2")

        # Instantiate Semantic Kernel agent objects
        search_agent = AzureAIAgent(client=client, definition=search_agent_def)
        # report_agent = AzureAIAgent(client=client, definition=report_agent_def)
        # validation_agent = AzureAIAgent(client=client, definition=validation_agent_def)

        # ----- Agent 1: Document Search Agent -----
        # An agent that searches health plan documents.
        thread = await client.agents.create_thread()
        user_query = "tell me about the northwind health plan"

        await search_agent.add_chat_message(
            thread_id=thread.id,
            message=user_query
        )
        response_doc = await search_agent.get_response(thread_id=thread.id)
        print("\n[Document Search Agent Response]")
        print(response_doc)

        # # ----- Agent 2: Report Agent -----
        # # An agent that writes detailed reports about health plans.
        # thread2 = await client.agents.create_thread()
        # await report_agent.add_chat_message(
        #     thread_id=thread2.id,
        #     message=f"Write a detailed report about the {user_query} plan. Make sure to include information about coverage exclusions. Here is the relevant information for the plan: {response_doc}."
        # )
        # response_report = await report_agent.get_response(thread_id=thread2.id)
        # print("\n[Report Agent Response]")
        # print(response_report)

        # # ----- Agent 3: Validation Agent -----
        # # An agent that runs validation checks to ensure the generated report meets requirements.
        # thread3 = await client.agents.create_thread()
        # await validation_agent.add_chat_message(
        #     thread_id=thread3.id,
        #     message=f"Validate that the generated report includes information about coverage exclusions. Here is the generated report: {response_report}"
        # )
        # response_validation = await validation_agent.get_response(thread_id=thread3.id)
        # print("\n[Validation Agent Response]")
        # print(response_validation)

        # ----- Optional Cleanup: Delete the conversation threads -----
        # for thread in [thread1, thread2, thread3]:
        #     try:
        #         await client.agents.delete_thread(thread.id)
        #     except Exception as e:
        #         print(f"❌ Error deleting thread {thread.id}: {e}")


if __name__ == "__main__":
    asyncio.run(main())