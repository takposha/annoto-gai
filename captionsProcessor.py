from configData import configVars
from transcriptLoader import TranscriptData
from topicExtractor import retrieveTopics
from questionGenerator import retrieveQuestions
from utils import printAndLog


def main():
    config = configVars()
    config.setFromEnv()

    printAndLog(f"Retrieving Transcript for {config.videoToUse}...")
    videoData = TranscriptData(config)

    printAndLog(f"Retrieving Topics for {config.videoToUse}...")
    topicModeller = retrieveTopics(config, videoData)
    topicModeller.printTopics()

    printAndLog(f"Retrieving Questions for {config.videoToUse}...")
    questionData = retrieveQuestions(config, topicModeller, videoData)
    questionData.printQuestions()

if __name__ == "__main__":
    main()