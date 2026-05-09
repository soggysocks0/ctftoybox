/* Customize this challenge:
 *   - Adjust buf size / win() body / prompts to fit your scenario
 *   - The flag is read from /flag.txt at runtime, set by CTF Manager
 *   - To change the bug class, swap gets() for strcpy(), scanf("%s", ...),
 *     read() with overflowing length, etc.
 */
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>

void win(void) {
    char flag[128];
    FILE *f = fopen("/flag.txt", "r");
    if (!f) { puts("flag missing"); _exit(1); }
    if (!fgets(flag, sizeof(flag), f)) { puts("read failed"); _exit(1); }
    fclose(f);
    printf("Congrats: %s", flag);
    fflush(stdout);
    _exit(0);
}

void vuln(void) {
    char buf[64];
    puts("Say something:");
    fflush(stdout);
    gets(buf);
    printf("You said: %s\n", buf);
}

int main(void) {
    setvbuf(stdout, NULL, _IONBF, 0);
    setvbuf(stdin,  NULL, _IONBF, 0);
    vuln();
    return 0;
}
