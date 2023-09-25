import asyncio
import json

import asyncpraw

async def main():
    reddit = asyncpraw.Reddit(
        client_id="_kvsvwkkrz16lqFWfh5RSg",
        client_secret="_pH-1gItjqUWbGKO5EtgqLcp4B7MzQ",
        password="ymv!hmd9xmg_tkb5GYF",
        user_agent="testscript by u/enturreopy",
        username="enturreopy",
    )
    submission = await reddit.submission(url="https://www.reddit.com/r/enturreopy/comments/xxuiyx/enturreopy/")
    print(submission.__dict__)
    # submission_json = json.dumps(submission.__dict__, indent=4, ensure_ascii=False)
    # print(submission_json)

asyncio.run(main())

