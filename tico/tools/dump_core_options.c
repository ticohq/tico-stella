/* Dumps the core options the libnx build of Stella reads as JSON on stdout.
 * Built and run on the host by tico_module.py, which copies the option table
 * out of src/os/libretro/libretro.cxx (where Stella defines it, inside
 * retro_set_environment) into stella_option_defs.h, so the module never
 * drifts from what the core accepts. Stella translates none of its options:
 * the other languages come out empty and tico_module.py supplies them. */
#include <stdio.h>

#include "libretro.h"
#include "stella_option_defs.h"

static void put_string(const char *s)
{
   putchar('"');
   for (; s && *s; s++)
   {
      if (*s == '"' || *s == '\\')
         putchar('\\');
      if (*s == '\n')
         fputs("\\n", stdout);
      else
         putchar(*s);
   }
   putchar('"');
}

static void dump(const char *name, const struct retro_core_option_v2_definition *defs, int last)
{
   const struct retro_core_option_v2_definition *def;
   printf("  ");
   put_string(name);
   printf(": [\n");
   for (def = defs; def && def->key; def++)
   {
      const struct retro_core_option_value *value;
      printf("    {\"key\": ");
      put_string(def->key);
      printf(", \"desc\": ");
      put_string(def->desc);
      printf(", \"info\": ");
      put_string(def->info);
      printf(", \"default\": ");
      put_string(def->default_value);
      printf(", \"values\": [");
      for (value = def->values; value->value; value++)
      {
         printf("%s[", value == def->values ? "" : ", ");
         put_string(value->value);
         printf(", ");
         /* an unlabelled choice is named by its value */
         put_string(value->label ? value->label : value->value);
         printf("]");
      }
      printf("]}%s\n", def[1].key ? "," : "");
   }
   printf("  ]%s\n", last ? "" : ",");
}

int main(void)
{
   /* tico's languages, by their lang/*.json name; only English is defined */
   static const char *languages[] = {"en", "de", "es", "fr", "ja", "pt", "ru", "zh"};
   const int count = sizeof(languages) / sizeof(languages[0]);
   int i;
   printf("{\n");
   for (i = 0; i < count; i++)
      dump(languages[i], i == 0 ? option_defs : NULL, i == count - 1);
   printf("}\n");
   return 0;
}
