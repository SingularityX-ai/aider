import os
from pathlib import Path

from aider import diffs

from ..dump import dump  # noqa: F401
from .base_coder import Coder
from .func_prompts import FunctionPrompts


class FunctionCoder(Coder):
    functions = [
        dict(
            name="write_file",
            description="create or update one or more files",
            parameters=dict(
                type="object",
                required=["explanation", "files"],
                properties=dict(
                    explanation=dict(
                        type="string",
                        description=(
                            "Step by step plan for the changes to be made to the code (future"
                            " tense, markdown format)"
                        ),
                    ),
                    files=dict(
                        type="array",
                        items=dict(
                            type="object",
                            required=["path", "content"],
                            properties=dict(
                                path=dict(
                                    type="string",
                                    description="Path of file to write",
                                ),
                                content=dict(
                                    type="string",
                                    description="Content to write to the file",
                                ),
                            ),
                        ),
                    ),
                ),
            ),
        ),
    ]

    def __init__(self, *args, **kwargs):
        self.gpt_prompts = FunctionPrompts()
        super().__init__(*args, **kwargs)

    def update_cur_messages(self, content, edited):
        if edited:
            self.cur_messages += [
                dict(role="assistant", content=self.gpt_prompts.redacted_edit_message)
            ]
        else:
            self.cur_messages += [dict(role="assistant", content=content)]

    def modify_incremental_response(self, final=False):
        args = self.parse_partial_args()

        if not args:
            return

        explanation = args.get("explanation")
        files = args.get("files", [])

        res = ""
        if explanation:
            res += f"{explanation}\n\n"

        for i, file_upd in enumerate(files):
            path = file_upd.get("path")
            if not path:
                continue
            content = file_upd.get("content")
            if not content:
                continue

            res += path + ":\n"

            this_final = (i < len(files) - 1) or final
            res += self.live_diffs(path, content, this_final)

        return res

    def live_diffs(self, fname, content, final):
        lines = content.splitlines(keepends=True)

        # ending an existing block
        full_path = os.path.abspath(os.path.join(self.root, fname))

        with open(full_path, "r") as f:
            orig_lines = f.readlines()

        show_diff = diffs.diff_partial_update(
            orig_lines,
            lines,
            final,
        ).splitlines()

        return "\n".join(show_diff)

    def update_files(self):
        args = self.parse_partial_args()

        if not args:
            return

        files = args.get("files", [])

        edited = set()
        for file_upd in files:
            path = file_upd.get("path")
            if not path:
                raise ValueError(f"Missing path: {file_upd}")

            content = file_upd.get("content")
            if not content:
                raise ValueError(f"Missing content: {file_upd}")

            full_path = os.path.abspath(os.path.join(self.root, path))
            Path(full_path).write_text(content)
            edited.add(path)

        return edited