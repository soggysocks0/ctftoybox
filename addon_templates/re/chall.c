/* Customize this challenge:
 *   - Edit `password` to whatever you want players to recover
 *   - Edit the welcome / failure / success messages
 *   - The {{FLAG}} placeholder is replaced by CTF Manager at deploy time
 *     using the flag_template in template.json.
 */
#include <stdio.h>
#include <string.h>

static const char password[] = "your_password_here";
static const char flag[]     = "{{FLAG}}";

int main(void) {
    char input[64];

    printf("=== My Custom Crackme ===\n");
    printf("Enter the password: ");
    if (!fgets(input, sizeof(input), stdin)) {
        return 1;
    }
    input[strcspn(input, "\r\n")] = 0;

    if (strcmp(input, password) == 0) {
        printf("Correct! %s\n", flag);
        return 0;
    }
    printf("Nope.\n");
    return 1;
}
