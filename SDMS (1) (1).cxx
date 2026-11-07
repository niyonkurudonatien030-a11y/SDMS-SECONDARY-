#include <stdio.h>
#include <string.h>
#include <ctype.h>

#define MAX_SUBJECTS 20
#define MAX_NAME 20

// Convert string to lowercase
void toLowerCase(char str[]) {
    for (int i = 0; str[i]; i++) {
        str[i] = tolower(str[i]);
    }
}

// Check if subject exists in array
int contains(char arr[][MAX_NAME], int size, char target[]) {
    for (int i = 0; i < size; i++) {
        if (strcmp(arr[i], target) == 0) {
            return 1;
        }
    }
    return 0;
}

int main() {
    char level;
    char subjects[MAX_SUBJECTS][MAX_NAME];
    char coreSubjects[3][MAX_NAME];

    int subjectCount = 0;
    float totalMarks = 0;

    printf("Wiga mu kihe cyiciro? Hitamo inyuguti:\n");
    printf("a. Amashuri Abanza\n");
    printf("b. Icyiciro rusange\n");
    printf("c. Icyiciro cya kabiri cy'Ayisumbuye\n");

    scanf(" %c", &level);
    level = tolower(level);

    switch (level) {
        case 'a':
            strcpy(subjects[subjectCount++], "math");
            strcpy(subjects[subjectCount++], "set");
            strcpy(subjects[subjectCount++], "socio");
            strcpy(subjects[subjectCount++], "eng");
            strcpy(subjects[subjectCount++], "kiny");
            strcpy(subjects[subjectCount++], "fra");
            strcpy(subjects[subjectCount++], "rel");
            strcpy(subjects[subjectCount++], "pes");
            strcpy(subjects[subjectCount++], "arts");
            strcpy(subjects[subjectCount++], "ict");
            break;

        case 'b':
            strcpy(subjects[subjectCount++], "math");
            strcpy(subjects[subjectCount++], "phy");
            strcpy(subjects[subjectCount++], "bio");
            strcpy(subjects[subjectCount++], "chem");
            strcpy(subjects[subjectCount++], "geo");
            strcpy(subjects[subjectCount++], "hist");
            strcpy(subjects[subjectCount++], "eship");
            strcpy(subjects[subjectCount++], "kiny");
            strcpy(subjects[subjectCount++], "eng");
            strcpy(subjects[subjectCount++], "fra");
            strcpy(subjects[subjectCount++], "ict");
            strcpy(subjects[subjectCount++], "pes");
            break;

        case 'c': {
            // Mandatory subjects
            strcpy(subjects[subjectCount++], "eng");
            strcpy(subjects[subjectCount++], "fra");
            strcpy(subjects[subjectCount++], "kiny");
            strcpy(subjects[subjectCount++], "ict");
            strcpy(subjects[subjectCount++], "gscs");
            strcpy(subjects[subjectCount++], "eship");

            printf("Andika amasomo y'ingenzi atatu:\n");

            for (int i = 0; i < 3; i++) {
                scanf("%s", coreSubjects[i]);
                toLowerCase(coreSubjects[i]);
                strcpy(subjects[subjectCount++], coreSubjects[i]);
            }

            int isMCB = contains(coreSubjects, 3, "math") &&
                        contains(coreSubjects, 3, "chem") &&
                        contains(coreSubjects, 3, "bio");

            int isPCB = contains(coreSubjects, 3, "phy") &&
                        contains(coreSubjects, 3, "chem") &&
                        contains(coreSubjects, 3, "bio");

            if (isMCB) {
                strcpy(subjects[subjectCount++], "phy");
            } else if (isPCB) {
                strcpy(subjects[subjectCount++], "math");
            }

            break;
        }

        default:
            printf("Icyiciro ntikibaho!\n");
            return 0;
    }

    // Enter marks
    for (int i = 0; i < subjectCount; i++) {
        float mark, max;

        printf("Andika amanota ya %s:\n", subjects[i]);
        scanf("%f", &mark);

        printf("Andika max marks:\n");
        scanf("%f", &max);

        if (max == 0) {
            printf("Max ntigomba kuba 0! Ongera wandike.\n");
            i--;
            continue;
        }

        totalMarks += (mark / max) * 100;
    }

    float overallPercentage = totalMarks / subjectCount;

    printf("\nWagize %.2f%% ku ijana mu masomo %d\n", overallPercentage, subjectCount);

    // Ranking
    if (overallPercentage >= 80) {
        printf("Urahebuje\n");
    } else if (overallPercentage >= 70) {
        printf("Urarenze\n");
    } else if (overallPercentage >= 60) {
        printf("Ni byiza\n");
    } else if (overallPercentage >= 50) {
        printf("Watsinze\n");
    } else {
        printf("Watsinzwe\n");
    }

    return 0;
}