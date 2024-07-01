import sys
import os
import logging
from datetime import datetime
from configData import outputFolder, LangChainBot
from utils import getMetadata, formatDocs, dataLoader, dataSaver

from typing import List
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_chroma import Chroma
from langchain_community.document_loaders import DataFrameLoader


class Question(BaseModel):
    """
    Represents a question formed by the model.

    Attributes:
        question (str): The question formed by the model.
        answers (List[str]): List of 4 possible answers to the question formed.
        correctAnswerIndex (int): Index of the correct answer to the question formed.
        reason (str): Explanation for the correct answer to the question formed.
        topic (str): Topic of the question formed.
        insertionTime (str): Timestamp at which the question is to be inserted within a transcript,
                             which is at the end of a relevant transcript section.
        citations (List[int]): The integer IDs of the specific sources which were used to form the question.
    """

    question: str = Field(title="Question", description="Question formed by the model.")
    answers: List[str] = Field(
        title="Answers",
        description="List of 4 possible answers to the question formed.",
    )
    correctAnswerIndex: int = Field(
        title="Correct Answer Index",
        description="Index of the correct answer to the question formed.",
    )
    reason: str = Field(
        title="Reason",
        description="Explanation for the correct answer to the question formed.",
    )
    topic: str = Field(title="Topic", description="Topic of the question formed.")
    insertionTime: str = Field(
        title="Insertion Time",
        description="Timestamp at which the question is to be inserted within a transcript, which is at the end of a relevant transcript section.",
    )
    citations: List[int] = Field(
        ...,
        description="The integer IDs of the SPECIFIC sources which was used to form the question.",
    )


class Questions(BaseModel):
    """
    Represents a collection of questions formed for a given transcript.
    """

    questions: List[Question] = Field(
        title="Questions",
        description="List of questions formed for a given transcript.",
    )

    def print(self):
        for i, question in enumerate(self.questions):
            print(f"Question {i+1}: {question.question}")
            print(f"Answers: {question.answers}")
            print(
                f"Correct Answer: {question.correctAnswerIndex}: {question.answers[question.correctAnswerIndex]}"
            )
            print(f"Reason: {question.reason}")
            print(f"Topic: {question.topic}")
            print(f"Insertion Time: {question.insertionTime}")
            print(f"Citations: {question.citations}")
            print("\n")


class LangChainQuestionData:
    """
    Represents a class that handles question data generation for the LangChainBot.

    Args:
        config: The configuration object for the question generation.
        videoData: Optional video data object.

    Attributes:
        config: The configuration object for the question generation.
        videoData: The video data object.
        LangChainQuestionBot: The LangChainBot instance.
        retriever: The retriever object for question generation.
        runnable: The runnable object for question generation.
        responseInfo: The Questions object containing the generated question data.

    Methods:
        initialize: Initializes the LangChainQuestionData object.
        makeQuestionData: Generates the question data.
        loadQuestionData: Loads the question data from a file.
        saveQuestionData: Saves the question data to a file.
        saveToFile: Saves the question data to a file.

    """

    def __init__(self, config, videoData=None):
        self.config = config
        self.videoData = videoData
        self.LangChainQuestionBot = None
        self.retriever = None
        self.runnable = None
        self.rawResponseInfo: Questions = None
        self.responseInfo = None

    def initialize(self, videoData):
        """
        Initializes the LangChainQuestionData object.

        Args:
            videoData: The video data object.

        """
        self.videoData = videoData
        self.LangChainQuestionBot = LangChainBot(self.config)
        self.retriever = makeRetriever(
            self.videoData.combinedTranscript,
            self.LangChainQuestionBot.embeddings,
            self.config.videoToUse,
        )
        self.runnable = makeRunnable(self.retriever, self.LangChainQuestionBot.client)

    def makeQuestionData(self, load=True):
        """
        Generates the question data.

        Args:
            load: Whether to load existing question data or generate new data.

        """
        if load:
            self.loadQuestionData()
        else:
            self.rawResponseInfo = self.runnable.invoke(f"{self.config.questionCount}")
            self.responseInfo = processResponseData(
                self.rawResponseInfo, self.videoData.combinedTranscript
            )

    def loadQuestionData(self):
        """
        Loads the question data from a file.
        """
        loadedData = dataLoader(
            self.config, "questionData", f" - {self.config.generationModel}"
        )
        if loadedData is None:
            loadedData = [None] * 1
        if len(loadedData) != 1:
            logging.warning(
                "Loaded data for Question Data is incomplete/broken. Data will be regenerated and saved."
            )
            loadedData = [None] * 1
        (self.responseInfo,) = loadedData

    def saveQuestionData(self):
        """
        Saves the question data to a file.
        """
        dataSaver(
            (self.responseInfo,),
            self.config,
            "questionData",
            f" - {self.config.generationModel}",
        )


def retrieveLangChainQuestions(config, videoData=None, overwrite=False):
    """
    Retrieves language chain questions based on the provided configuration and video data.

    Args:
        config (Config): The configuration object containing the settings for question generation.
        videoData (VideoData, optional): The video data object containing information about the video. Defaults to None.
        overwrite (bool, optional): Whether to overwrite existing question data. Defaults to False.

    Returns:
        LangChainQuestionData: The generated language chain question data.
    """
    questionData = LangChainQuestionData(config)
    if not config.overwriteQuestionData and not overwrite:
        questionData.makeQuestionData(load=True)

        if questionData.responseInfo is not None:
            logging.info("Question Data loaded from saved files.")
            logging.info(f"Question Data Count: {len(questionData.responseInfo)}")
            return questionData

    if videoData is None:
        logging.error(
            "No saved data was found, and no video data was provided in function call needed to extract topics."
        )
        sys.exit("Video Data not provided. Exiting...")
    else:
        questionData.initialize(videoData)

    logging.info("Generating Question Data...")
    questionData.makeQuestionData(load=False)
    questionData.saveQuestionData()

    logging.info("Question Data generated and saved for current configuration.")
    logging.info(f"Question Data Count: {len(questionData.responseInfo)}")
    return questionData


def makeRetriever(transcript, embeddings, collectionName) -> Chroma:
    """
    Creates a retriever object using the given transcript, embeddings, and collection name.

    Args:
        transcript (str): The transcript to be used for creating the retriever.
        embeddings: The embeddings to be used for creating the retriever.
        collectionName (str): The name of the collection. 
        In this case we use the name of the video or parent folder.
        This refers to `VIDEO_TO_USE` in the config file, or the `videoToUse` attribute in the `configVars` class.

    Returns:
        Chroma: The retriever object.

    The collectionName matches the video name or parent folder name.
    This is done to ensure that each transcript is associated with a unique retriever object.
    So any data generated from the retriever can be associated with the correct video or parent folder.
    """

    collectionName = collectionName.replace(" ", "_")
    transcript = getMetadata(transcript)
    loader = DataFrameLoader(transcript, page_content_column="Combined Lines")
    vectorstore = Chroma.from_documents(
        documents=loader.load(), embedding=embeddings, collection_name=collectionName
    )
    retriever = vectorstore.as_retriever()
    return retriever


def makeRunnable(retriever, client):
    """
    Creates a runnable object that generates multiple-choice questions based on a provided transcription text.

    Args:
        retriever: The retriever object used to extract relevant information from the transcription text.
        client: The client object used to generate the multiple-choice questions.

    Returns:
        A runnable object that can be executed to generate multiple-choice questions.

    Example usage:
        retriever = ...
        client = ...
        runnable = makeRunnable(retriever, client)
        questions = runnable.invoke(f"{questionCount}")
    """
    template = """You are a question-generating algorithm.
                Only extract relevant information from the provided trancription text: {context}
                Generate {count} Multiple-Choice Questions with 4 possible answers for each question, and provide a reason for the correct answer.
                Provide an appropriate timestamp to show where each question would be inserted within the transcript.
                This is at the end of the relevant text section used to form the question, using the metadata information.
                Try to cover a wide range of topics covered in the tranacription text.
                The questions should be in line with the overall theme of the text."""
    prompt = ChatPromptTemplate.from_template(template)
    runnable = (
        {"context": retriever | formatDocs, "count": RunnablePassthrough()}
        | prompt
        | client.with_structured_output(schema=Questions)
    )
    return runnable


def processResponseData(responseInfo, transcript):
    """
    Process the response data and return a dictionary of processed information.

    Args:
        responseInfo (object): The response information object.
        transcript (pandas.DataFrame): The transcript data.

    Returns:
        dict: A dictionary containing the processed data.

    """
    processedData = {}
    for index, question in enumerate(responseInfo.questions):
        citationData = transcript.iloc[question.citations[0]]
        processedData[index] = {
            "Start": datetime.strptime(citationData["Start"], "%H:%M:%S"),
            "End": datetime.strptime(citationData["End"], "%H:%M:%S"),
            "Topic": question.topic,
            "Question": question.question,
            "Answers": question.answers,
            "Correct Answer Index": question.correctAnswerIndex,
            "Reason": question.reason,
        }

    return processedData
