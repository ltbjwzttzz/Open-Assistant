from itertools import zip_longest
from random import shuffle

from model_training.custom_datasets.entities import Language, Mode
from pydantic import BaseModel, validator
from pydantic.fields import ModelField

QA_SPECIAL_TOKENS = {
    "Question": "<|prompter|>",
    "Answer": "<|assistant|>",
    "System": "<|system|>",
    "StartPrefix": "<|prefix_begin|>",
    "EndPrefix": "<|prefix_end|>",
}


def format_system_prefix(prefix, eos_token):
    return "{}{}{}".format(
        QA_SPECIAL_TOKENS["System"],
        prefix,
        eos_token,
    )


class DatasetEntry(BaseModel):
    questions: list[str]
    answers: list[str]
    context: str | None
    lang: Language | None
    length: int | None
    quality: float | None
    humor: float | None
    creativity: float | None

    @validator("length")
    def above_zero(cls, v) -> int:
        if v is not None and v < 0:
            raise ValueError(f"Length cannot be lower than 0. Received {v}")
        return v

    @validator("quality", "humor", "creativity")
    def between_0_1(cls, v, field: ModelField) -> float:
        if v is not None and not (0 <= v <= 1):
            raise ValueError(f"Field {field.name} must be between 0 and 1. Received {v}.")
        return round(v, 1)

    def system_tag(self, eos_token: str) -> str | None:
        relevant_system_infos = [
            (k, v)
            for k, v in self.__dict__.items()
            if k not in ["questions", "answers"] and v is not None and str(v).replace("\n", "")
        ]
        if len(relevant_system_infos) > 0:
            shuffle(relevant_system_infos)
            system_tag_key_values = "\n".join([f"{k}: {v}" for k, v in relevant_system_infos])
            system_tag = f"{QA_SPECIAL_TOKENS['System']}{system_tag_key_values}\n{eos_token}"
            return system_tag

    def get_formatted(self, mode: Mode, eos_token: str) -> str | list[str]:
        system_tag = self.system_tag(eos_token)
        if mode == Mode.rl:
            if system_tag is not None:
                return f"{system_tag}{QA_SPECIAL_TOKENS['Question']}{self.questions[0]}{QA_SPECIAL_TOKENS['Answer']}"
            else:
                return f"{QA_SPECIAL_TOKENS['Question']}{self.questions[0]}{QA_SPECIAL_TOKENS['Answer']}"
        if system_tag is not None:
            qa_list = [system_tag]
        else:
            qa_list = list()
        for q, a in zip_longest(self.questions, self.answers):
            match (q, a):
                case (str(), str()):
                    qa_list.extend(
                        [
                            f"{QA_SPECIAL_TOKENS['Question']}{q}{eos_token}",
                            f"{QA_SPECIAL_TOKENS['Answer']}{a}{eos_token}",
                        ]
                    )
                case (str(), None):
                    qa_list.append(f"{QA_SPECIAL_TOKENS['Question']}{q}{eos_token}")
                case (None, None):
                    break
                case (None, str()):
                    raise ValueError("Received answer without getting corresponding question. Aborting")
        if mode == Mode.sft:
            return qa_list
        elif mode == Mode.rm:
            raise NotImplementedError("This is currently not implemented.")

    @classmethod
    def create_from_prompter_assistant_interplay(cls, qa: dict[str, str]):
        """Creates a DatasetEntry from a qa of given structure. Even if qa contains consecutative assistant or prompter phrases.


        Returns:
            self: DatasetEntry class
        """
        # todo: implement
        NotImplementedError("Function not implemented currently.")


def format_pairs(
    pairs: list[str] | DatasetEntry, eos_token: str, add_initial_reply_token: str = False, mode: Mode | None = None
) -> list[str]:
    if isinstance(pairs, DatasetEntry) and mode is not None:
        return pairs.get_formatted(mode=mode, eos_token=eos_token)
    else:
        # backwards compatibility
        conversations = [
            "{}{}{}".format(QA_SPECIAL_TOKENS["Question" if i % 2 == 0 else "Answer"], pairs[i], eos_token)
            for i in range(len(pairs))
        ]
        if add_initial_reply_token:
            conversations.append(QA_SPECIAL_TOKENS["Answer"])
        return conversations


def format_rl_text(pairs: list[str]) -> str:
    # convert question answer pairs to only the prefix prompt for RLHF
    return "{}{}{}".format(QA_SPECIAL_TOKENS["Question"], pairs[0], QA_SPECIAL_TOKENS["Answer"])


def format_reply(text: str, eos_token: str) -> str:
    return "{}{}{}".format(QA_SPECIAL_TOKENS["Answer"], text, eos_token)
